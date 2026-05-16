// =============================================================================
// EX-DIGITAL — Login Page
// =============================================================================

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Loader2, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../lib/apiClient';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier || !password) return;

    setLoading(true);
    try {
      // Auto-detect email vs matric number
      const isEmail = identifier.includes('@');
      const payload = isEmail
        ? { email: identifier, password }
        : { matric_number: identifier, password };

      const data = await authApi.login(payload);
      setAuth(data.access_token, {
        id: data.user_id,
        email: identifier,
        full_name: data.full_name,
        role: data.role as 'admin' | 'lecturer' | 'student',
      });
      toast.success(`Welcome back, ${data.full_name.split(' ')[0]}!`);

      // Role-based redirect
      if (data.role === 'admin') navigate('/admin');
      else if (data.role === 'lecturer') navigate('/lecturer');
      else navigate('/student');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {[...Array(6)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full opacity-10"
            style={{
              width: `${150 + i * 80}px`,
              height: `${150 + i * 80}px`,
              left: `${(i * 17) % 100}%`,
              top: `${(i * 23) % 100}%`,
              background: i % 2 === 0
                ? 'radial-gradient(circle, #6b5fff, transparent)'
                : 'radial-gradient(circle, #00d4ff, transparent)',
            }}
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.05, 0.15, 0.05],
            }}
            transition={{ duration: 4 + i, repeat: Infinity, ease: 'easeInOut' }}
          />
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4 animate-float"
            style={{
              background: 'linear-gradient(135deg, #6b5fff, #9747ff)',
              boxShadow: '0 0 40px rgba(107,95,255,0.5)',
            }}
          >
            <ShieldCheck className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="font-display text-3xl font-bold gradient-text">EX-DIGITAL</h1>
          <p className="text-white/50 text-sm mt-1">Attendance Management System</p>
        </div>

        {/* Card */}
        <div className="glass-card p-8">
          <h2 className="font-display text-xl font-semibold text-white mb-1">Sign In</h2>
          <p className="text-white/40 text-sm mb-6">
            Enter your email, matric number, or student ID
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                Email / Matric Number
              </label>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="admin@ex-digital.edu or CS/2020/001"
                className="input-glass"
                required
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-glass pr-12"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <motion.button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 mt-2"
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
            >
              {loading ? (
                <><Loader2 size={16} className="animate-spin" /> Signing in...</>
              ) : (
                'Sign In'
              )}
            </motion.button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 pt-5 border-t border-white/10">
            <p className="text-xs text-white/35 text-center mb-3">Demo credentials</p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { role: 'Admin', id: 'admin@ex.edu', pw: 'Admin1234' },
                { role: 'Lecturer', id: 'lecturer@ex.edu', pw: 'Lect1234' },
                { role: 'Student', id: 'CS/2024/001', pw: 'Student1234' },
              ].map((d) => (
                <button
                  key={d.role}
                  type="button"
                  onClick={() => { setIdentifier(d.id); setPassword(d.pw); }}
                  className="demo-cred-btn text-center py-2 px-1.5 rounded-lg text-xs transition-all"
                >
                  <div className="font-semibold text-primary-300">{d.role}</div>
                  <div className="text-white/30 text-[10px] mt-0.5 truncate">{d.id}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-center text-white/25 text-xs mt-6">
          © 2026 EX-DIGITAL · Secured by JWT + bcrypt
        </p>
      </motion.div>
    </div>
  );
}
