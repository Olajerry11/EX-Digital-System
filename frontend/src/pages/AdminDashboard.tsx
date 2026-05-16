// EX-DIGITAL — Admin Dashboard
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Users, BookOpen, CalendarCheck, BarChart3, PlusCircle, Upload, RefreshCw, LogOut, Shield } from 'lucide-react';
import toast from 'react-hot-toast';
import { adminApi } from '../lib/apiClient';
import { useAuthStore } from '../store/authStore';
import NetworkStatusPill from '../components/NetworkStatusPill';

interface Stats { total_users: number; total_students: number; total_lecturers: number; total_courses: number; active_sessions_today: number; overall_attendance_rate: number; }
interface User { id: string; email: string; full_name: string; role: string; matric_number: string | null; is_active: boolean; }

export default function AdminDashboard() {
  const { user, logout } = useAuthStore();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'courses'>('overview');
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/immutability
  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, u] = await Promise.all([adminApi.stats(), adminApi.users()]);
      setStats(s); setUsers(u);
    } catch { toast.error('Failed to load data.'); }
    finally { setLoading(false); }
  };

  const handleDeactivate = async (id: string, name: string) => {
    try { await adminApi.deactivateUser(id); toast.success(`${name} deactivated.`); loadData(); }
    catch { toast.error('Failed to deactivate user.'); }
  };

  const statCards = stats ? [
    { label: 'Total Users', value: stats.total_users, icon: Users, color: '#6b5fff' },
    { label: 'Students', value: stats.total_students, icon: Users, color: '#00d4ff' },
    { label: 'Lecturers', value: stats.total_lecturers, icon: Shield, color: '#9747ff' },
    { label: 'Active Courses', value: stats.total_courses, icon: BookOpen, color: '#00ff87' },
    { label: 'Sessions Today', value: stats.active_sessions_today, icon: CalendarCheck, color: '#ff47b8' },
    { label: 'Attendance Rate', value: `${stats.overall_attendance_rate}%`, icon: BarChart3, color: '#ffa940' },
  ] : [];

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 backdrop-blur-md border-b border-white/10 header-dark-bg">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #6b5fff, #9747ff)' }}>
              <Shield size={16} className="text-white" />
            </div>
            <span className="font-display font-bold gradient-text">EX-DIGITAL</span>
            <span className="badge-purple ml-1">Admin</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-white/50 text-sm hidden md:block">{user?.full_name}</span>
            <button onClick={logout} className="btn-secondary py-2 px-3 flex items-center gap-1.5 text-sm"><LogOut size={14} /> Sign Out</button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6">
        <div className="flex gap-2 mb-6 flex-wrap">
          {(['overview', 'users', 'courses'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-5 py-2 rounded-lg text-sm font-medium capitalize transition-all ${activeTab === tab ? 'bg-primary-600/80 text-white border border-primary-500/50' : 'text-white/50 hover:text-white/80 hover:bg-white/5'}`}>
              {tab}
            </button>
          ))}
          <button onClick={loadData} className="ml-auto btn-secondary py-2 px-3 flex items-center gap-1.5 text-sm">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {activeTab === 'overview' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <h2 className="font-display text-2xl font-bold text-white mb-1">System Overview</h2>
            <p className="text-white/40 text-sm mb-6">Real-time metrics across all departments.</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
              {statCards.map(c => (
                <motion.div key={c.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="stat-card">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${c.color}22` }}>
                    <c.icon size={20} style={{ color: c.color }} />
                  </div>
                  <div className="mt-3">
                    <div className="text-2xl font-bold font-display text-white">{loading ? '—' : c.value}</div>
                    <div className="text-xs text-white/45 mt-0.5">{c.label}</div>
                  </div>
                </motion.div>
              ))}
            </div>
            <div className="glass-card p-5">
              <h3 className="font-semibold text-white mb-4 flex items-center gap-2"><Users size={16} className="text-primary-400" /> Recent Users</h3>
              <div className="space-y-3">
                {users.slice(0, 5).map(u => (
                  <div key={u.id} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                    <div><div className="text-sm font-medium text-white">{u.full_name}</div><div className="text-xs text-white/40">{u.email}</div></div>
                    <span className={u.role === 'admin' ? 'badge-purple' : u.role === 'lecturer' ? 'badge-blue' : 'badge-green'}>{u.role}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'users' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <h2 className="font-display text-2xl font-bold text-white">User Management</h2>
              <div className="flex gap-2">
                <button className="btn-secondary py-2 px-4 flex items-center gap-1.5 text-sm"><Upload size={14} /> Import CSV</button>
                <button className="btn-primary py-2 px-4 flex items-center gap-1.5 text-sm"><PlusCircle size={14} /> Add User</button>
              </div>
            </div>
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-white/10">
                    {['Name', 'Email', 'Role', 'Matric', 'Status', 'Actions'].map(h => (
                      <th key={h} className={`px-4 py-3 text-white/50 font-medium ${h === 'Actions' ? 'text-right' : 'text-left'}`}>{h}</th>
                    ))}
                  </tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id} className="border-b border-white/5 hover:bg-white/3 transition-colors">
                        <td className="px-4 py-3 text-white font-medium">{u.full_name}</td>
                        <td className="px-4 py-3 text-white/60">{u.email}</td>
                        <td className="px-4 py-3"><span className={u.role === 'admin' ? 'badge-purple' : u.role === 'lecturer' ? 'badge-blue' : 'badge-green'}>{u.role}</span></td>
                        <td className="px-4 py-3 text-white/40 font-mono text-xs">{u.matric_number || '—'}</td>
                        <td className="px-4 py-3">{u.is_active ? <span className="badge-green">Active</span> : <span className="badge-red">Inactive</span>}</td>
                        <td className="px-4 py-3 text-right">{u.is_active && u.role !== 'admin' && <button onClick={() => handleDeactivate(u.id, u.full_name)} className="text-xs text-red-400 hover:text-red-300 transition-colors">Deactivate</button>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'courses' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-2xl font-bold text-white">Course Management</h2>
              <button className="btn-primary py-2 px-4 flex items-center gap-1.5 text-sm"><PlusCircle size={14} /> New Course</button>
            </div>
            <div className="glass-card p-8 text-center">
              <BookOpen size={40} className="mx-auto text-white/20 mb-3" />
              <p className="text-white/40 text-sm">Course CRUD — connects to /courses API</p>
            </div>
          </motion.div>
        )}
      </div>
      <NetworkStatusPill />
    </div>
  );
}
