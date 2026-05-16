// EX-DIGITAL — Student Dashboard (QR Scanner + History)
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { QrCode, CheckCircle2, XCircle, LogOut, WifiOff, Loader2, BarChart3 } from 'lucide-react';
import toast from 'react-hot-toast';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { attendanceApi, coursesApi } from '../lib/apiClient';
import { useAuthStore } from '../store/authStore';
import { queueScan, syncOfflineQueue, getQueueCount, type SyncProgress } from '../lib/offlineQueue';
import { useNetworkStatus } from '../lib/useNetworkStatus';
import NetworkStatusPill from '../components/NetworkStatusPill';

interface CourseHistory { course_id: string; course_code: string; course_title: string; total_sessions: number; attended: number; attendance_percentage: number; }
interface Course { id: string; code: string; title: string; term: string; }

export default function StudentDashboard() {
  const { user, logout } = useAuthStore();
  const isOnline = useNetworkStatus();
  const [tab, setTab] = useState<'scan' | 'history'>('scan');
  const [scanning, setScanning] = useState(false);
  const [history, setHistory] = useState<CourseHistory[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null);
  const [queueCount, setQueueCount] = useState(0);
  const scannerRef = useRef<Html5QrcodeScanner | null>(null);
  const [lastScanResult, setLastScanResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // useCallback versions for use by manual triggers (not called directly in effects)
  const refreshQueueCount = useCallback(async () => {
    const c = await getQueueCount();
    setQueueCount(c);
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [h, c] = await Promise.all([attendanceApi.myHistory(), coursesApi.list()]);
      setHistory(h as CourseHistory[]);
      setCourses(c as Course[]);
    } catch {
      // Silently fail — network may be unavailable
    }
  }, []);

  // Initial data load — inline async to avoid transitive-setState lint rule
  useEffect(() => {
    const init = async () => {
      try {
        const [h, c] = await Promise.all([attendanceApi.myHistory(), coursesApi.list()]);
        setHistory(h as CourseHistory[]);
        setCourses(c as Course[]);
        const count = await getQueueCount();
        setQueueCount(count);
      } catch {
        // Silently fail on mount
      }
    };
    void init();

  }, []); // intentionally run once on mount

  // Sync when coming back online — check queue count fresh to avoid stale closure
  useEffect(() => {
    if (!isOnline) return;
    const checkAndSync = async () => {
      const count = await getQueueCount();
      if (count > 0) {
        await syncOfflineQueue(setSyncProgress);
        await refreshQueueCount();
      }
    };
    void checkAndSync();
  }, [isOnline, refreshQueueCount]);

  const startScanner = () => {
    setScanning(true);
    setLastScanResult(null);
    setTimeout(() => {
      scannerRef.current = new Html5QrcodeScanner('qr-reader', { fps: 10, qrbox: 250 }, false);
      scannerRef.current.render(handleScanSuccess, () => { /* ignore scan errors */ });
    }, 100);
  };

  const stopScanner = () => {
    scannerRef.current?.clear().catch(() => { /* ignore clear errors */ });
    scannerRef.current = null;
    setScanning(false);
  };

  const handleScanSuccess = async (decodedText: string) => {
    stopScanner();
    const match = decodedText.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);
    if (!match) { toast.error('Invalid QR code.'); return; }
    const sessionUuid = match[1];
    const timestamp = new Date().toISOString();

    if (!isOnline) {
      await queueScan({ session_uuid: sessionUuid, timestamp });
      setLastScanResult({ ok: true, msg: 'Scan saved offline — will sync when connected.' });
      setQueueCount(prev => prev + 1);
      toast('Scan queued offline', { icon: '📶' });
      return;
    }

    try {
      const res = await attendanceApi.rapidScan([{ session_uuid: sessionUuid, timestamp }]);
      const item = res.results[0] as { result: string; message: string };
      if (item.result === 'accepted') {
        setLastScanResult({ ok: true, msg: `✓ Attendance recorded (${item.message})` });
        toast.success('Attendance recorded!');
        void loadData();
      } else {
        setLastScanResult({ ok: false, msg: item.message });
        toast.error(item.message);
      }
    } catch {
      toast.error('Scan failed. Retry.');
    }
  };

  const progressColor = (pct: number) =>
    pct >= 75 ? 'progress-fill-green' : pct >= 50 ? 'progress-fill-yellow' : 'progress-fill-red';

  return (
    <div className="min-h-screen max-w-lg mx-auto">
      <header className="sticky top-0 z-40 backdrop-blur-md border-b border-white/10 header-student-bg">
        <div className="px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-display font-bold gradient-text">EX-DIGITAL</span>
            <span className="badge-green">Student</span>
            {!isOnline && <span className="badge-red flex items-center gap-1 text-[10px]"><WifiOff size={8} /> Offline</span>}
          </div>
          <div className="flex items-center gap-2">
            {queueCount > 0 && <span className="sync-badge">{queueCount} pending</span>}
            <button onClick={logout} aria-label="Sign out" title="Sign out"
              className="text-white/40 hover:text-white/70 transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {syncProgress?.status === 'syncing' && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            className="sync-progress-bar px-4 py-2">
            <div className="flex items-center gap-2 text-xs text-accent-blue">
              <Loader2 size={12} className="animate-spin" />
              Syncing {syncProgress.synced}/{syncProgress.total} offline scans…
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="px-4 py-6">
        <div className="mb-2">
          <h1 className="font-display text-xl font-bold text-white">Hi, {user?.full_name?.split(' ')[0]} 👋</h1>
          <p className="text-white/40 text-sm">Scan a QR code to mark your attendance</p>
        </div>

        <div className="flex gap-2 mb-6 mt-4">
          {(['scan', 'history'] as const).map(t => (
            <button key={t} onClick={() => { setTab(t); if (scanning) stopScanner(); }}
              className={`flex-1 py-2.5 rounded-xl text-sm font-medium capitalize transition-all ${tab === t ? 'bg-primary-600/80 text-white' : 'text-white/50 hover:text-white/80 glass-card'}`}>
              {t === 'scan' ? <><QrCode size={14} className="inline mr-1.5" />Scanner</> : <><BarChart3 size={14} className="inline mr-1.5" />History</>}
            </button>
          ))}
        </div>

        {tab === 'scan' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            {!scanning ? (
              <motion.button onClick={startScanner} whileTap={{ scale: 0.97 }}
                className="w-full glass-card p-12 flex flex-col items-center gap-4 cursor-pointer hover:border-primary-500/50 transition-all group">
                <div className="qr-trigger-inner w-20 h-20 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform animate-pulse-glow">
                  <QrCode size={36} className="text-primary-400" />
                </div>
                <div className="text-center">
                  <div className="font-semibold text-white mb-1">Tap to Scan</div>
                  <div className="text-white/40 text-sm">Point camera at the session QR code</div>
                </div>
              </motion.button>
            ) : (
              <div className="space-y-3">
                <div className="qr-frame overflow-hidden rounded-2xl">
                  <div id="qr-reader" className="w-full" />
                </div>
                <button onClick={stopScanner} className="btn-secondary w-full py-2.5 text-sm">Cancel</button>
              </div>
            )}

            <AnimatePresence>
              {lastScanResult && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className={`flex items-start gap-3 p-4 rounded-xl border ${lastScanResult.ok ? 'border-green-500/30 bg-green-500/10' : 'border-red-500/30 bg-red-500/10'}`}>
                  {lastScanResult.ok
                    ? <CheckCircle2 size={18} className="text-green-400 flex-shrink-0 mt-0.5" />
                    : <XCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />}
                  <p className="text-sm text-white/80">{lastScanResult.msg}</p>
                </motion.div>
              )}
            </AnimatePresence>

            {courses.length > 0 && (
              <div className="mt-4">
                <h3 className="text-xs font-medium text-white/40 uppercase tracking-wide mb-3">Enrolled Courses</h3>
                <div className="space-y-2">
                  {courses.map(c => (
                    <div key={c.id} className="glass-card p-3 flex items-center justify-between">
                      <div><span className="font-mono text-xs text-primary-300 font-semibold">{c.code}</span><span className="text-white/50 text-xs ml-2">{c.title}</span></div>
                      <span className="text-white/30 text-xs">{c.term}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {tab === 'history' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
            {history.length === 0 && (
              <div className="glass-card p-8 text-center">
                <BarChart3 size={32} className="mx-auto text-white/15 mb-3" />
                <p className="text-white/40 text-sm">No attendance history yet</p>
              </div>
            )}
            {history.map(h => (
              <motion.div key={h.course_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-mono text-sm font-bold text-primary-300">{h.course_code}</div>
                    <div className="text-white/60 text-xs mt-0.5">{h.course_title}</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-2xl font-bold font-display ${h.attendance_percentage >= 75 ? 'text-green-400' : h.attendance_percentage >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {h.attendance_percentage}%
                    </div>
                    <div className="text-white/30 text-[10px]">{h.attended}/{h.total_sessions} sessions</div>
                  </div>
                </div>
                <div className="progress-track h-1.5 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-700 ${progressColor(h.attendance_percentage)}`}
                    style={{ width: `${h.attendance_percentage}%` }} />
                </div>
                {h.attendance_percentage < 75 && <p className="text-red-400 text-xs mt-2">⚠ Below 75% — at risk</p>}
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
      <NetworkStatusPill />
    </div>
  );
}
