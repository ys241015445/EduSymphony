import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { useLanguageStore, Locale } from '../../stores/languageStore'
import { useT } from '../../i18n/translations'
import Button from '../ui/Button'
import { BookOpen, LogOut, LayoutDashboard, Globe } from 'lucide-react'

const LOCALE_OPTIONS: { value: Locale; key: string }[] = [
  { value: 'zh-CN', key: 'nav.lang_zh_cn' },
  { value: 'zh-TW', key: 'nav.lang_zh_tw' },
  { value: 'en', key: 'nav.lang_en' },
]

export default function Header() {
  const { user, token, logout } = useAuthStore()
  const { locale, setLocale } = useLanguageStore()
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

  const currentLabel = LOCALE_OPTIONS.find((o) => o.value === locale)

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-100">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-gray-900 hover:text-brand-600 transition-colors">
          <BookOpen className="w-6 h-6 text-brand-600" />
          <span className="text-lg font-semibold tracking-tight">EduSymphony</span>
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
              <Link to="/dashboard">
                <Button variant="ghost" size="sm">
                  <LayoutDashboard className="w-4 h-4 mr-1.5" />
                  {t('nav.workspace')}
                </Button>
              </Link>
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
