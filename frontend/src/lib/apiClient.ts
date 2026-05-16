// =============================================================================
// EX-DIGITAL — Axios API Client with JWT & Retry Logic
// =============================================================================

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { useAuthStore } from '../store/authStore';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Create axios instance
// ---------------------------------------------------------------------------
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ---------------------------------------------------------------------------
// Request interceptor — attach JWT
// ---------------------------------------------------------------------------
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor — handle 401 globally
// ---------------------------------------------------------------------------
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Retry with exponential backoff (3 retries, 1s/2s/4s delays)
// ---------------------------------------------------------------------------
async function withRetry<T>(
  fn: () => Promise<T>,
  retries = 3,
  delayMs = 1000
): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    if (retries === 0) throw err;
    const isNetworkError = !axios.isAxiosError(err) || !err.response;
    if (!isNetworkError) throw err; // Don't retry 4xx errors
    await new Promise((r) => setTimeout(r, delayMs));
    return withRetry(fn, retries - 1, delayMs * 2);
  }
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------
export interface LoginPayload {
  email?: string;
  matric_number?: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  role: string;
  full_name: string;
}

export const authApi = {
  login: (data: LoginPayload) =>
    withRetry(() => api.post<TokenResponse>('/auth/login', data).then((r) => r.data)),
  me: () =>
    withRetry(() => api.get('/auth/me').then((r) => r.data)),
  register: (data: object) =>
    withRetry(() => api.post('/auth/register', data).then((r) => r.data)),
  resetPassword: (data: object) =>
    withRetry(() => api.post('/auth/reset-password', data).then((r) => r.data)),
  bulkImport: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/auth/bulk-import', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },
};

// ---------------------------------------------------------------------------
// Courses API
// ---------------------------------------------------------------------------
export const coursesApi = {
  list: () => withRetry(() => api.get('/courses/').then((r) => r.data)),
  get: (id: string) => withRetry(() => api.get(`/courses/${id}`).then((r) => r.data)),
  create: (data: object) => withRetry(() => api.post('/courses/', data).then((r) => r.data)),
  update: (id: string, data: object) =>
    withRetry(() => api.patch(`/courses/${id}`, data).then((r) => r.data)),
  enroll: (id: string, studentIds: string[]) =>
    withRetry(() => api.post(`/courses/${id}/enroll`, { student_ids: studentIds }).then((r) => r.data)),
  assignLecturer: (id: string, lecturerId: string) =>
    withRetry(() => api.post(`/courses/${id}/assign-lecturer`, { lecturer_id: lecturerId }).then((r) => r.data)),
  attendanceStats: (id: string) =>
    withRetry(() => api.get(`/courses/${id}/attendance/stats`).then((r) => r.data)),
};

// ---------------------------------------------------------------------------
// Sessions API
// ---------------------------------------------------------------------------
export const sessionsApi = {
  start: (data: { course_id: string; duration_minutes?: number }) =>
    withRetry(() => api.post('/sessions/start', data).then((r) => r.data)),
  active: () => withRetry(() => api.get('/sessions/active').then((r) => r.data)),
  end: (id: string) => withRetry(() => api.post(`/sessions/${id}/end`).then((r) => r.data)),
  attendees: (id: string) => withRetry(() => api.get(`/sessions/${id}/attendees`).then((r) => r.data)),
};

// ---------------------------------------------------------------------------
// Attendance API
// ---------------------------------------------------------------------------
export interface ScanItem {
  session_uuid: string;
  timestamp: string;
}

export const attendanceApi = {
  rapidScan: (scans: ScanItem[]) =>
    withRetry(() => api.post('/attendance/rapid-scan', { scans }).then((r) => r.data)),
  manualMark: (data: { session_id: string; student_id: string; note?: string }) =>
    withRetry(() => api.post('/attendance/manual', data).then((r) => r.data)),
  myHistory: () => withRetry(() => api.get('/attendance/my').then((r) => r.data)),
};

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------
export const adminApi = {
  stats: () => withRetry(() => api.get('/admin/dashboard/stats').then((r) => r.data)),
  users: (role?: string) =>
    withRetry(() => api.get('/admin/users', { params: role ? { role } : undefined }).then((r) => r.data)),
  getUser: (id: string) => withRetry(() => api.get(`/admin/users/${id}`).then((r) => r.data)),
  updateUser: (id: string, data: object) =>
    withRetry(() => api.patch(`/admin/users/${id}`, data).then((r) => r.data)),
  deactivateUser: (id: string) =>
    withRetry(() => api.delete(`/admin/users/${id}`).then((r) => r.data)),
};

export default api;
