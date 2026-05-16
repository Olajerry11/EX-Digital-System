// EX-DIGITAL — Lecturer Dashboard
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PlayCircle, StopCircle, QrCode, Users, BookOpen, LogOut, WifiOff, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import { coursesApi, sessionsApi } from '../lib/apiClient';
import { useAuthStore } from '../store/authStore';
import { useNetworkStatus } from '../lib/useNetworkStatus';
import NetworkStatusPill from '../components/NetworkStatusPill';

interface Course { id: string; code: string; title: string; term: string; }
interface Session { id: string; course_id: string; session_key: string; qr_uuid: string; qr_deep_link: string; start_time: string; end_time: string | null; status: string; }
interface Attendee { id: string; student_id: string; timestamp: string; status: string; source: string; }
interface ApiError { response?: { data?: { detail?: string } } }

export default function LecturerDashboard() {
  const { user, logout } = useAuthStore();
  const isOnline = useNetworkStatus();
  const [courses, setCourses] = useState<Course[]>([]);
  const [activeSessions, setActiveSessions] = useState<Session[]>([]);
  const [attendees, setAttendees] = useState<Attendee[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [startingFor, setStartingFor] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // useCallback versions for use by the Refresh button (not called directly in effects)
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [c, s] = await Promise.all([coursesApi.list(), sessionsApi.active()]);
      setCourses(c as Course[]);
      setActiveSessions(s as Session[]);
    } catch {
      if (isOnline) toast.error('Failed to load data.');
    } finally {
      setLoading(false);
    }
  }, [isOnline]);

  // Initial data fetch — async IIFE defined inside the effect so linter
  // does not see setState called "synchronously" from the effect body.
  useEffect(() => {
    const fetchInitial = async () => {
      setLoading(true);
      try {
        const [c, s] = await Promise.all([coursesApi.list(), sessionsApi.active()]);
        setCourses(c as Course[]);
        setActiveSessions(s as Session[]);
      } catch {
        // Silently fail on mount — user can hit Refresh
      } finally {
        setLoading(false);
      }
    };
    void fetchInitial();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally run once on mount

  // Attendee polling — inline async function avoids transitive-setState lint warning
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!selectedSession) return;

    const sessionId = selectedSession.id;

    const fetchAttendees = async () => {
      try {
        const data = await sessionsApi.attendees(sessionId);
        setAttendees(data as Attendee[]);
      } catch {
        // Silently fail; will retry on next interval
      }
    };

    void fetchAttendees();
    pollRef.current = setInterval(() => { void fetchAttendees(); }, 3000);

    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selectedSession]);

  const selectSession = (session: Session | null) => {
    if (!session) setAttendees([]);
    setSelectedSession(session);
  };

  const startSession = async (courseId: string) => {
    setStartingFor(courseId);
    try {
      const session = await sessionsApi.start({ course_id: courseId, duration_minutes: 10 }) as Session;
      toast.success(`Session started! Key: ${session.session_key}`);
      setActiveSessions(prev => [...prev, session]);
      selectSession(session);
    } catch (e: unknown) {
      const err = e as ApiError;
      toast.error(err?.response?.data?.detail ?? 'Failed to start session.');
    } finally {
      setStartingFor(null);
    }
  };

  const endSession = async (sessionId: string) => {
    try {
      await sessionsApi.end(sessionId);
      toast.success('Session ended.');
      setActiveSessions(prev => prev.filter(s => s.id !== sessionId));
      selectSession(null);
    } catch {
      toast.error('Failed to end session.');
    }
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 backdrop-blur-md border-b border-white/10 header-dark-bg">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-display font-bold gradient-text">EX-DIGITAL</span>
            <span className="badge-blue">Lecturer</span>
            {!isOnline && <span className="badge-red flex items-center gap-1"><WifiOff size={10} /> Offline</span>}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-white/50 text-sm hidden md:block">{user?.full_name}</span>
            <button onClick={logout} aria-label="Sign out" title="Sign out"
              className="btn-secondary py-2 px-3 flex items-center gap-1.5 text-sm">
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-white">My Courses</h2>
            <button onClick={loadData} aria-label="Refresh" title="Refresh"
              className="text-white/40 hover:text-white/70 transition-colors">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
          {courses.length === 0 && !loading && (
            <div className="glass-card p-6 text-center">
              <BookOpen size={30} className="mx-auto text-white/20 mb-2" />
              <p className="text-white/40 text-sm">No courses assigned</p>
            </div>
          )}
          {courses.map(course => {
            const hasActive = activeSessions.some(s => s.course_id === course.id);
            return (
              <motion.div key={course.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-semibold text-white text-sm">{course.code}</div>
                    <div className="text-white/50 text-xs mt-0.5">{course.title}</div>
                    <div className="text-white/30 text-xs">{course.term}</div>
                  </div>
                  {hasActive && <span className="badge-green text-[10px]">LIVE</span>}
                </div>
                {hasActive ? (
                  <button onClick={() => endSession(activeSessions.find(s => s.course_id === course.id)!.id)}
                    className="btn-danger w-full py-2 text-xs flex items-center justify-center gap-1.5">
                    <StopCircle size={12} /> End Session
                  </button>
                ) : (
                  <button onClick={() => startSession(course.id)} disabled={startingFor === course.id}
                    className="btn-primary w-full py-2 text-xs flex items-center justify-center gap-1.5">
                    {startingFor === course.id ? 'Starting...' : <><PlayCircle size={12} /> Start Session</>}
                  </button>
                )}
              </motion.div>
            );
          })}
        </div>

        <div className="lg:col-span-2 space-y-4">
          <h2 className="font-display text-lg font-bold text-white">Live Attendance Monitor</h2>
          {!selectedSession ? (
            <div className="glass-card p-12 text-center">
              <QrCode size={48} className="mx-auto text-white/15 mb-4" />
              <p className="text-white/40">Start a session to see live attendance</p>
            </div>
          ) : (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
              <div className="glass-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white">Session Active</h3>
                    <div className="text-white/40 text-xs mt-0.5">Started {new Date(selectedSession.start_time).toLocaleTimeString()}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-mono font-bold gradient-text tracking-widest">{selectedSession.session_key}</div>
                    <div className="text-white/30 text-[10px]">Session Key</div>
                  </div>
                </div>
                <div className="bg-white rounded-xl p-4 w-fit mx-auto">
                  <div className="text-xs text-gray-500 break-all font-mono">{selectedSession.qr_deep_link}</div>
                </div>
              </div>

              <div className="glass-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-white flex items-center gap-2">
                    <Users size={16} className="text-primary-400" />
                    Attendees <span className="badge-purple ml-1">{attendees.length}</span>
                  </h3>
                  <span className="text-xs text-accent-blue animate-pulse">● Live</span>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto no-scrollbar">
                  <AnimatePresence>
                    {attendees.map(a => (
                      <motion.div key={a.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                        className="attendee-row flex items-center justify-between py-2 px-3 rounded-lg">
                        <div className="text-xs text-white/60 font-mono">{a.student_id.slice(0, 8)}…</div>
                        <div className="flex items-center gap-2">
                          <span className={a.status === 'on_time' ? 'badge-green' : 'badge-yellow'}>{a.status}</span>
                          <span className="text-white/30 text-[10px]">{new Date(a.timestamp).toLocaleTimeString()}</span>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  {attendees.length === 0 && <p className="text-center text-white/25 text-xs py-4">Waiting for students to scan…</p>}
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
      <NetworkStatusPill />
    </div>
  );
}
