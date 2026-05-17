// =============================================================================
// EX-DIGITAL — App Entry Point
// =============================================================================
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import './index.css';

import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import AdminDashboard from './pages/AdminDashboard';
import LecturerDashboard from './pages/LecturerDashboard';
import StudentDashboard from './pages/StudentDashboard';
import ProtectedRoute from './components/ProtectedRoute';

import { startBackgroundSync } from './lib/offlineQueue';

// Start background sync engine globally
startBackgroundSync();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/admin" element={
          <ProtectedRoute allowedRoles={['admin']}>
            <AdminDashboard />
          </ProtectedRoute>
        } />
        <Route path="/lecturer" element={
          <ProtectedRoute allowedRoles={['lecturer']}>
            <LecturerDashboard />
          </ProtectedRoute>
        } />
        <Route path="/student" element={
          <ProtectedRoute allowedRoles={['student']}>
            <StudentDashboard />
          </ProtectedRoute>
        } />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: 'rgba(20, 20, 40, 0.95)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255,255,255,0.13)',
          color: 'white',
          borderRadius: '12px',
        },
        success: { iconTheme: { primary: '#00ff87', secondary: '#001a0e' } },
        error: { iconTheme: { primary: '#ff4060', secondary: '#fff' } },
      }}
    />
  </React.StrictMode>
);
