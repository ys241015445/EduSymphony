import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { useLanguageStore, Locale } from '../../stores/languageStore'
import { useT } from '../../i18n/translations'
import Button from '../ui/Button'
import JobsBadge from './JobsBadge'
import { canUseCourseTools, parseAccessLevel, isAdmin } from '../../lib/access'
import { BookOpen, LogOut, LayoutDashboard, Globe, Files, Shield } from 'lucide-react'

const LOCALE_OPTIONS: { value: Locale; key: string }[] = [
  { value: 'zh-CN', key: 'nav.lang_zh_cn' },
  { value: 'zh-TW', key: 'nav.lang_zh_tw' },
  { value: 'en', key: 'nav.lang_en' },
]

export default function Header() {
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.token)
  const logout = useAuthStore((s) => s.logout)
  const locale = useLanguageStore((s) => s.locale)
  const setLocale = useLanguageStore((s) => s.setLocale)
  const navigate = useNavigate()
  const t = useT()

  const [langOpen, setLangOpen] = useState(false)
  const langRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(e.target as Node)) setLangOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const access = parseAccessLevel(user?.access_level)
  const showToolsJobs = user ? canUseCourseTools(access) : false
  const showAdmin = user ? isAdmin(access) : false
  const currentLabel = LOCALE_OPTIONS.find((o) => o.value === locale)

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-gray-900 hover:text-brand-600 transition-colors">
          <BookOpen className="w-6 h-6 text-brand-600" />
          <span className="text-lg font-semibold tracking-tight">{t('nav.brand')}</span>
        </Link>

        <nav className="flex items-center gap-3">
          {/* Language Switcher */}
          <div ref={langRef} className="relative">
            <button
              onClick={() => setLangOpen((v) => !v)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <Globe className="w-3.5 h-3.5" />
              {currentLabel ? t(currentLabel.key) : ''}
            </button>
            {langOpen && (
              <div className="absolute right-0 mt-1 w-28 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                {LOCALE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => { setLocale(opt.value); setLangOpen(false) }}
                    className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                      locale === opt.value
                        ? 'text-brand-600 bg-brand-50 font-semibold'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {t(opt.key)}
                  </button>
                ))}
              </div>
            )}
          </div>

          {token && user ? (
            <>
              {showToolsJobs && <JobsBadge />}
              <Link to="/dashboard">
                <Button variant="ghost" size="sm">
                  <LayoutDashboard className="w-4 h-4 mr-1.5" />
                  {t('nav.workspace')}
                </Button>
              </Link>
              <Link to="/documents">
                <Button variant="ghost" size="sm">
                  <Files className="w-4 h-4 mr-1.5" />
                  {t('dashboard.documents')}
                </Button>
              </Link>
              {showAdmin && (
                <Link to="/admin/users">
                  <Button variant="ghost" size="sm">
                    <Shield className="w-4 h-4 mr-1.5" />
                    {t('nav.admin_users')}
                  </Button>
                </Link>
              )}
              {access !== 'admin' && !user.export_pay_exempt && (
                <span className="text-xs px-2 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                  {t('header.export_credits')}: {user.export_credits ?? 0}
                </span>
              )}
              <span className="text-sm text-gray-500">{user.username}</span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-1.5" />
                {t('nav.logout')}
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">{t('nav.login')}</Button>
              </Link>
              <Link to="/login">
                <Button size="sm">{t('nav.get_started')}</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
