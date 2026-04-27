import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { useT } from '../i18n/translations'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { BookOpen, ArrowLeft } from 'lucide-react'

export default function Auth() {
  const t = useT()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || t('auth.error_default'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-brand-600 text-white flex-col justify-between p-12">
        <div>
          <Link to="/" className="flex items-center gap-2 text-white/90 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">{t('auth.back_home')}</span>
          </Link>
        </div>
        <div>
          <BookOpen className="w-12 h-12 mb-6 text-white/80" />
          <h2 className="text-3xl font-bold mb-4">
            {t('auth.hero_title_1')}
            <br />
            {t('auth.hero_title_2')}
          </h2>
          <p className="text-white/70 leading-relaxed max-w-md">
            {t('auth.hero_desc')}
          </p>
        </div>
        <div className="text-white/40 text-sm">
          &copy; {new Date().getFullYear()} EduSymphony
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8">
            <Link to="/" className="flex items-center gap-2 text-gray-500 hover:text-gray-700 text-sm mb-6">
              <ArrowLeft className="w-4 h-4" />
              {t('auth.back_home')}
            </Link>
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {t('auth.welcome_back')}
          </h1>
          <p className="text-gray-500 text-sm mb-8">
            {t('auth.login_subtitle')}
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label={t('auth.username')}
              placeholder={t('auth.username_placeholder')}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <Input
              label={t('auth.password')}
              type="password"
              placeholder={t('auth.password_placeholder')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? t('auth.processing') : t('auth.login')}
            </Button>
          </form>
          <p className="mt-6 text-xs text-gray-400 text-center">
            {t('auth.contact_admin')}
          </p>
        </div>
      </div>
    </div>
  )
}
