import { Link } from 'react-router-dom'
import { Lock, ArrowLeft } from 'lucide-react'
import Header from '../layout/Header'
import Card from '../ui/Card'
import { useT } from '../../i18n/translations'

/**
 * Shared placeholder for any sub-route of /semester-helper accessed by a user
 * without `can_semester_helper`. Shown instead of silently redirecting so the
 * teacher knows the module exists and can ask an admin to enable it.
 */
export default function LockedComingSoon({ moduleTitle }: { moduleTitle?: string }) {
  const t = useT()
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-2xl mx-auto px-6 py-12">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600 inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('semester_helper.back_dashboard')}
          </Link>
        </div>
        <Card className="py-14 text-center">
          <div className="w-14 h-14 rounded-full bg-amber-50 mx-auto mb-4 flex items-center justify-center">
            <Lock className="w-7 h-7 text-amber-500" />
          </div>
          <h1 className="text-xl font-semibold text-gray-800 mb-1">
            {moduleTitle || t('semester_helper.title')}
          </h1>
          <p className="text-sm text-amber-700 font-medium mt-2">
            {t('semester_helper.locked_title')}
          </p>
          <p className="text-sm text-gray-500 max-w-md mx-auto mt-2 leading-relaxed">
            {t('semester_helper.locked_desc')}
          </p>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 mt-6 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('semester_helper.back_dashboard')}
          </Link>
        </Card>
      </main>
    </div>
  )
}
