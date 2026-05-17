// =============================================================================
// EX-DIGITAL — Registration Page
// =============================================================================

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Loader2, ShieldCheck, ArrowLeft } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate, Link } from 'react-router-dom';
import { authApi } from '../lib/apiClient';
import { useAuthStore } from '../store/authStore';

export default function RegisterPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<'student' | 'lecturer'>('student');
  const [matricNumber, setMatricNumber] = useState('');
  
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !fullName) return;
    if (role === 'student' && !matricNumber) {
      toast.error('Matric Number is required for students.');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        email,
        password,
        full_name: fullName,
        role,
        matric_number: role === 'student' ? matricNumber : undefined,
      };

      const data = await authApi.selfRegister(payload);
      setAuth(data.access_token, {
        id: data.user_id,
        email: email,
        full_name: data.full_name,
        role: data.role as 'admin' | 'lecturer' | 'student',
      });
      toast.success(`Account created successfully! Welcome, ${data.full_name.split(' ')[0]}!`);

      // Role-based redirect
      if (data.role === 'admin') navigate('/admin');
      else if (data.role === 'lecturer') navigate('/lecturer');
      else navigate('/student');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string | any[] } } })?.response?.data?.detail;
      
      let errorMsg = 'Registration failed. Please check your inputs.';
      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Handle Pydantic validation errors
        errorMsg = detail[0].message || errorMsg;
      }
      
      toast.error(errorMsg);
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
        className="w-full max-w-md z-10"
      >
        {/* Logo */}
        <div className="text-center mb-6">
          <motion.div
            className="inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-3 animate-float"
            style={{
              background: 'linear-gradient(135deg, #6b5fff, #9747ff)',
              boxShadow: '0 0 30px rgba(107,95,255,0.4)',
            }}
          >
            <ShieldCheck className="w-6 h-6 text-white" />
          </motion.div>
          <h1 className="font-display text-2xl font-bold gradient-text">EX-DIGITAL</h1>
        </div>

        {/* Card */}
        <div className="glass-card p-6 sm:p-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="font-display text-xl font-semibold text-white mb-1">Create Account</h2>
              <p className="text-white/40 text-sm">Join the digital campus</p>
            </div>
            <Link to="/login" className="text-white/50 hover:text-white transition-colors flex items-center gap-1 text-sm">
              <ArrowLeft size={16} /> Back
            </Link>
          </div>

          <form onSubmit={handleRegister} className="space-y-4">
            
            {/* Role Selection */}
            <div className="flex bg-white/5 p-1 rounded-xl border border-white/10 mb-4">
              <button
                type="button"
                onClick={() => setRole('student')}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
                  role === 'student' 
                    ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30 shadow-[0_0_15px_rgba(107,95,255,0.2)]' 
                    : 'text-white/40 hover:text-white/70'
                }`}
              >
                Student
              </button>
              <button
                type="button"
                onClick={() => setRole('lecturer')}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
                  role === 'lecturer' 
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30 shadow-[0_0_15px_rgba(0,212,255,0.2)]' 
                    : 'text-white/40 hover:text-white/70'
                }`}
              >
                Lecturer
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. John Doe"
                className="input-glass"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="john@ex-digital.edu"
                className="input-glass"
                required
              />
            </div>

            {role === 'student' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Matric Number
                </label>
                <input
                  type="text"
                  value={matricNumber}
                  onChange={(e) => setMatricNumber(e.target.value)}
                  placeholder="CS/2024/001"
                  className="input-glass uppercase"
                  required={role === 'student'}
                />
              </motion.div>
            )}

            <div>
              <label className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 chars, 1 uppercase, 1 number"
                  className="input-glass pr-12"
                  required
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
              className="btn-primary w-full flex items-center justify-center gap-2 mt-6"
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
            >
              {loading ? (
                <><Loader2 size={16} className="animate-spin" /> Creating Account...</>
              ) : (
                'Register Now'
              )}
            </motion.button>
          </form>

        </div>

        <p className="text-center text-white/25 text-xs mt-6">
          © 2026 EX-DIGITAL · Secured by JWT + bcrypt
        </p>
      </motion.div>
    </div>
  );
}
