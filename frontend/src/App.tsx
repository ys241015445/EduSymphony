import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Banner from './components/layout/Banner'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import LessonCreate from './pages/LessonCreate'
import QuickGenerate from './pages/QuickGenerate'
import LessonProcess from './pages/LessonProcess'
import LessonResult from './pages/LessonResult'
import SeriesCreate from './pages/SeriesCreate'
import SeriesDashboard from './pages/SeriesDashboard'
import CourseTools from './pages/CourseTools'
import CourseToolsLibrary from './pages/CourseToolsLibrary'
import UniversityCreate from './pages/UniversityCreate'
import UniversityDashboard from './pages/UniversityDashboard'
import TemplateFill from './pages/TemplateFill'
import DocumentsLibrary from './pages/DocumentsLibrary'
import DocumentEditor from './pages/DocumentEditor'
import { parseAccessLevel, isLimited, isAdmin } from './lib/access'
import AdminUsers from './pages/AdminUsers'
import AdminUserStorage from './pages/AdminUserStorage'
import { Toaster } from './components/ui/Toast'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function LimitedRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (isLimited(parseAccessLevel(user?.access_level))) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!isAdmin(parseAccessLevel(user?.access_level))) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <>
    <Banner />
    <Toaster />
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
      <Route
        path="/series/new"
        element={
          <ProtectedRoute>
            <SeriesCreate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/series/:id"
        element={
          <ProtectedRoute>
            <SeriesDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/course-tools/library"
        element={
          <ProtectedRoute>
            <LimitedRoute>
              <CourseToolsLibrary />
            </LimitedRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/course-tools/:lessonId?"
        element={
          <ProtectedRoute>
            <LimitedRoute>
              <CourseTools />
            </LimitedRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/university/new"
        element={
          <ProtectedRoute>
            <UniversityCreate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/university/:id"
        element={
          <ProtectedRoute>
            <UniversityDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/template-fill"
        element={
          <ProtectedRoute>
            <LimitedRoute>
              <TemplateFill />
            </LimitedRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users/:userId/storage"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminUserStorage />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <AdminUsers />
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <DocumentsLibrary />
          </ProtectedRoute>
        }
      />
      <Route
        path="/documents/version/:versionId"
        element={
          <ProtectedRoute>
            <DocumentEditor />
          </ProtectedRoute>
        }
      />
    </Routes>
    </>
  )
}
