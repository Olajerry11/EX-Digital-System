// =============================================================================
// EX-DIGITAL — Zustand Auth Store
// =============================================================================

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type UserRole = 'admin' | 'lecturer' | 'student';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
        window.location.href = '/login';
      },
    }),
    {
      name: 'exdigital-auth',
      // Only persist token + user (not the whole state)
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
