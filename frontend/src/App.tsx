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
import { Toaster } from './components/ui/Toast'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
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
            <CourseToolsLibrary />
          </ProtectedRoute>
        }
      />
      <Route
        path="/course-tools/:lessonId?"
        element={
          <ProtectedRoute>
            <CourseTools />
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
            <TemplateFill />
          </ProtectedRoute>
        }
      />
    </Routes>
    </>
  )
}
