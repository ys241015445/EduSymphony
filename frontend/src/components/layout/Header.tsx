import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import Button from '../ui/Button'
import { BookOpen, LogOut, LayoutDashboard } from 'lucide-react'

export default function Header() {
  const { user, token, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-gray-900 hover:text-brand-600 transition-colors">
          <BookOpen className="w-6 h-6 text-brand-600" />
          <span className="text-lg font-semibold tracking-tight">EduSymphony</span>
        </Link>

        <nav className="flex items-center gap-3">
          {token && user ? (
            <>
              <Link to="/dashboard">
                <Button variant="ghost" size="sm">
                  <LayoutDashboard className="w-4 h-4 mr-1.5" />
                  工作台
                </Button>
              </Link>
              <span className="text-sm text-gray-500">{user.username}</span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-1.5" />
                退出
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">登录</Button>
              </Link>
              <Link to="/login">
                <Button size="sm">免费开始</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
