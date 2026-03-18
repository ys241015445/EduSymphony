import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import LessonCreate from './pages/LessonCreate'
import QuickGenerate from './pages/QuickGenerate'
import LessonProcess from './pages/LessonProcess'
import LessonResult from './pages/LessonResult'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Auth />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/lesson/new"
        element={
          <ProtectedRoute>
            <LessonCreate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/quick-generate"
        element={
          <ProtectedRoute>
            <QuickGenerate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/lesson/:id/process"
        element={
          <ProtectedRoute>
            <LessonProcess />
          </ProtectedRoute>
        }
      />
      <Route
        path="/lesson/:id/result"
        element={
          <ProtectedRoute>
            <LessonResult />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
