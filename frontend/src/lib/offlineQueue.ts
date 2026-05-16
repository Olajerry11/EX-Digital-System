// =============================================================================
// EX-DIGITAL — Offline Queue Manager (IndexedDB via idb)
// =============================================================================
// Manages queued attendance scans when the device is offline.
// Uses IndexedDB for persistence across page refreshes.
// Background sync: flushes queue to /attendance/rapid-scan on reconnection.
// =============================================================================

import { openDB, type IDBPDatabase } from 'idb';
import { attendanceApi, type ScanItem } from './apiClient';

const DB_NAME = 'exdigital-offline';
const DB_VERSION = 1;
const STORE_SCANS = 'queued-scans';
const STORE_MANUAL = 'queued-manual';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface QueuedScan {
  id?: number;
  session_uuid: string;
  timestamp: string;
  queued_at: string;
}

export interface QueuedManualMark {
  id?: number;
  session_id: string;
  student_id: string;
  note?: string;
  queued_at: string;
}

export type SyncProgress = {
  total: number;
  synced: number;
  failed: number;
  status: 'idle' | 'syncing' | 'done' | 'error';
};

// ---------------------------------------------------------------------------
// DB Initializer
// ---------------------------------------------------------------------------
let dbPromise: Promise<IDBPDatabase> | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_SCANS)) {
          db.createObjectStore(STORE_SCANS, { keyPath: 'id', autoIncrement: true });
        }
        if (!db.objectStoreNames.contains(STORE_MANUAL)) {
          db.createObjectStore(STORE_MANUAL, { keyPath: 'id', autoIncrement: true });
        }
      },
    });
  }
  return dbPromise;
}

// ---------------------------------------------------------------------------
// Scan Queue Operations
// ---------------------------------------------------------------------------
export async function queueScan(scan: Omit<QueuedScan, 'id' | 'queued_at'>): Promise<void> {
  const db = await getDb();
  await db.add(STORE_SCANS, {
    ...scan,
    queued_at: new Date().toISOString(),
  });
}

export async function getPendingScans(): Promise<QueuedScan[]> {
  const db = await getDb();
  return db.getAll(STORE_SCANS);
}

export async function clearSyncedScans(ids: number[]): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(STORE_SCANS, 'readwrite');
  await Promise.all(ids.map((id) => tx.store.delete(id)));
  await tx.done;
}

// ---------------------------------------------------------------------------
// Manual Mark Queue Operations
// ---------------------------------------------------------------------------
export async function queueManualMark(mark: Omit<QueuedManualMark, 'id' | 'queued_at'>): Promise<void> {
  const db = await getDb();
  await db.add(STORE_MANUAL, {
    ...mark,
    queued_at: new Date().toISOString(),
  });
}

export async function getPendingManualMarks(): Promise<QueuedManualMark[]> {
  const db = await getDb();
  return db.getAll(STORE_MANUAL);
}

export async function clearSyncedManualMarks(ids: number[]): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(STORE_MANUAL, 'readwrite');
  await Promise.all(ids.map((id) => tx.store.delete(id)));
  await tx.done;
}

// ---------------------------------------------------------------------------
// Sync Engine — flushes queue to server in batches
// ---------------------------------------------------------------------------
export async function syncOfflineQueue(
  onProgress?: (progress: SyncProgress) => void
): Promise<SyncProgress> {
  const scans = await getPendingScans();
  const manualMarks = await getPendingManualMarks();
  const total = scans.length + manualMarks.length;

  if (total === 0) {
    return { total: 0, synced: 0, failed: 0, status: 'done' };
  }

  onProgress?.({ total, synced: 0, failed: 0, status: 'syncing' });

  let synced = 0;
  let failed = 0;

  // ── Sync queued scans in batches of 50 ─────────────────────────────────────
  const BATCH_SIZE = 50;
  for (let i = 0; i < scans.length; i += BATCH_SIZE) {
    const batch = scans.slice(i, i + BATCH_SIZE);
    const scanItems: ScanItem[] = batch.map((s) => ({
      session_uuid: s.session_uuid,
      timestamp: s.timestamp,
    }));

    try {
      await attendanceApi.rapidScan(scanItems);
      const ids = batch.map((s) => s.id!).filter(Boolean);
      await clearSyncedScans(ids);
      synced += batch.length;
      onProgress?.({ total, synced, failed, status: 'syncing' });
    } catch {
      failed += batch.length;
      onProgress?.({ total, synced, failed, status: 'syncing' });
    }
  }

  // ── Sync queued manual marks ───────────────────────────────────────────────
  for (const mark of manualMarks) {
    try {
      await attendanceApi.manualMark({
        session_id: mark.session_id,
        student_id: mark.student_id,
        note: mark.note,
      });
      await clearSyncedManualMarks([mark.id!]);
      synced++;
      onProgress?.({ total, synced, failed, status: 'syncing' });
    } catch {
      failed++;
    }
  }

  const finalStatus = failed > 0 ? 'error' : 'done';
  const result: SyncProgress = { total, synced, failed, status: finalStatus };
  onProgress?.(result);
  return result;
}

// ---------------------------------------------------------------------------
// Network Status Monitor + Background Sync
// ---------------------------------------------------------------------------
let syncInterval: ReturnType<typeof setInterval> | null = null;

export function startBackgroundSync(
  onProgress?: (p: SyncProgress) => void
): () => void {
  // Sync on reconnection
  const handleOnline = () => {
    console.log('[EX-DIGITAL] Network restored. Starting offline queue sync...');
    syncOfflineQueue(onProgress).catch(console.error);
  };

  window.addEventListener('online', handleOnline);

  // Periodic sync every 30s when online
  syncInterval = setInterval(() => {
    if (navigator.onLine) {
      syncOfflineQueue(onProgress).catch(console.error);
    }
  }, 30_000);

  // Cleanup function
  return () => {
    window.removeEventListener('online', handleOnline);
    if (syncInterval) clearInterval(syncInterval);
  };
}

// ---------------------------------------------------------------------------
// Queue count (for badge display)
// ---------------------------------------------------------------------------
export async function getQueueCount(): Promise<number> {
  const [scans, marks] = await Promise.all([getPendingScans(), getPendingManualMarks()]);
  return scans.length + marks.length;
}
