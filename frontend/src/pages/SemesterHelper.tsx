import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { hasCapability } from '../lib/access'
import LockedComingSoon from '../components/semester/LockedComingSoon'
import {
  CalendarRange,
  ArrowLeft,
  Sparkles,
  Loader2,
  AlertTriangle,
  GraduationCap,
  ChevronRight,
  History,
} from 'lucide-react'

type PingState = 'loading' | 'ok' | 'forbidden' | 'error'

/**
 * Semester Material Assistant — hub page listing sub-modules.
 *
 * Users without `can_semester_helper` see a LockedComingSoon placeholder
 * instead of being silently redirected to /dashboard. Admins (lzf, ys)
 * bypass the capability check automatically.
 */
export default function SemesterHelper() {
  const t = useT()
  const user = useAuthStore((s) => s.user)
  const allowed = hasCapability(user as any, 'can_semester_helper')
  const [pingState, setPingState] = useState<PingState>('loading')

  useEffect(() => {
    if (!allowed) return
    let cancelled = false
    api.get('/api/v1/semester-helper/ping')
      .then(() => { if (!cancelled) setPingState('ok') })
      .catch((err) => {
        if (cancelled) return
        const code = err?.response?.status
        setPingState(code === 403 ? 'forbidden' : 'error')
      })
    return () => { cancelled = true }
  }, [allowed])

  if (!allowed) {
    return <LockedComingSoon />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-10">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600 inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('semester_helper.back_dashboard')}
          </Link>
        </div>

        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center shrink-0">
            <CalendarRange className="w-5 h-5 text-amber-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t('semester_helper.title')}</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">{t('semester_helper.subtitle')}</p>

        <div className="mb-3 text-sm font-medium text-gray-700">
          {t('semester_helper.modules_title')}
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Link to="/semester-helper/zhuke" className="group">
            <Card className="p-5 h-full hover:shadow-md hover:border-brand-300 transition-all">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center shrink-0 group-hover:bg-brand-100 transition-colors">
                  <GraduationCap className="w-5 h-5 text-brand-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-semibold text-gray-900 truncate">
                      {t('semester_helper.module_zhuke_title')}
                    </h2>
                    <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                    {t('semester_helper.module_zhuke_desc')}
                  </p>
                </div>
              </div>
            </Card>
          </Link>
          <Link to="/semester-helper/zhuke/history" className="group">
            <Card className="p-5 h-full hover:shadow-md hover:border-brand-300 transition-all">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center shrink-0 group-hover:bg-amber-100 transition-colors">
                  <History className="w-5 h-5 text-amber-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-semibold text-gray-900 truncate">
                      {t('semester_helper.module_zhuke_history_title')}
                    </h2>
                    <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
                  </div>
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">
                    {t('semester_helper.module_zhuke_history_desc')}
                  </p>
                </div>
              </div>
            </Card>
          </Link>
        </div>

        <div className="mt-8 text-xs text-gray-400 flex items-center gap-2">
          {pingState === 'loading' && (<><Loader2 className="w-3 h-3 animate-spin" /> {t('semester_helper.ping_loading')}</>)}
          {pingState === 'ok' && (<><Sparkles className="w-3 h-3 text-green-500" /> {t('semester_helper.ping_ok')}</>)}
          {pingState === 'forbidden' && (<><AlertTriangle className="w-3 h-3 text-amber-500" /> {t('semester_helper.ping_forbidden')}</>)}
          {pingState === 'error' && (<><AlertTriangle className="w-3 h-3 text-red-500" /> {t('semester_helper.ping_error')}</>)}
        </div>
      </main>
    </div>
  )
}
