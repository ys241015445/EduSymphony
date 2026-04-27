import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useLessonStore, LessonSummary } from '../stores/lessonStore'
import { useT } from '../i18n/translations'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Plus, FileText, Clock, CheckCircle2, AlertCircle, Loader2, Trash2, Zap, BookOpen, Wrench, GraduationCap, FileEdit, Library } from 'lucide-react'
import { useJobsStore } from '../stores/jobsStore'

const statusConfig: Record<string, { labelKey: string; color: string; icon: any }> = {
  queued: { labelKey: 'dashboard.status.queued', color: 'text-yellow-600 bg-yellow-50', icon: Clock },
  processing: { labelKey: 'dashboard.status.processing', color: 'text-blue-600 bg-blue-50', icon: Loader2 },
  completed: { labelKey: 'dashboard.status.completed', color: 'text-green-600 bg-green-50', icon: CheckCircle2 },
  failed: { labelKey: 'dashboard.status.failed', color: 'text-red-600 bg-red-50', icon: AlertCircle },
  draft: { labelKey: 'dashboard.status.draft', color: 'text-gray-600 bg-gray-50', icon: FileText },
}

function LessonCard({ lesson }: { lesson: LessonSummary }) {
  const t = useT()
  const { deleteLesson, fetchLessons } = useLessonStore()
  const navigate = useNavigate()
  const cfg = statusConfig[lesson.status] || statusConfig.draft
  const Icon = cfg.icon

  const handleClick = () => {
    if (lesson.status === 'completed') {
      navigate(`/lesson/${lesson.id}/result`)
    } else if (lesson.status === 'processing' || lesson.status === 'queued') {
      navigate(`/lesson/${lesson.id}/process`)
    }
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (window.confirm(t('dashboard.confirm_delete'))) {
      await deleteLesson(lesson.id)
      fetchLessons()
    }
  }

  return (
    <Card className="cursor-pointer hover:shadow-md hover:border-brand-200 transition-all duration-200 group" padding={false}>
      <div onClick={handleClick} className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
            <Icon className="w-3.5 h-3.5" />
            {t(cfg.labelKey)}
          </div>
          <button
            onClick={handleDelete}
            className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 transition-all"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
        <h3 className="font-semibold text-gray-900 mb-1 truncate">{lesson.title}</h3>
        <p className="text-sm text-gray-500">
          {lesson.subject} · {lesson.grade_level}
        </p>
        {lesson.status === 'processing' && (
          <div className="mt-3">
            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full transition-all duration-500"
                style={{ width: `${lesson.progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">{lesson.progress}%</p>
          </div>
        )}
        {lesson.created_at && (
          <p className="text-xs text-gray-400 mt-3">
            {new Date(lesson.created_at).toLocaleDateString()}
          </p>
        )}
      </div>
    </Card>
  )
}

export default function Dashboard() {
  const t = useT()
  const { lessons, loading, fetchLessons } = useLessonStore()
  const jobs = useJobsStore((s) => s.items)
  const bindSocket = useJobsStore((s) => s.bindSocket)
  const refreshJobs = useJobsStore((s) => s.refreshFromServer)

  useEffect(() => {
    fetchLessons()
    bindSocket()
    refreshJobs()
  }, [fetchLessons, bindSocket, refreshJobs])

  const activeJobs = jobs.filter((j) => j.status === 'queued' || j.status === 'running')

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('dashboard.subtitle')}</p>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/quick-generate">
              <Button variant="secondary" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                <Zap className="w-4 h-4 mr-1.5" />
                {t('dashboard.quick')}
              </Button>
            </Link>
            <Link to="/series/new">
              <Button variant="secondary" className="!border-violet-300 !text-violet-700 !bg-violet-50 hover:!bg-violet-100">
                <BookOpen className="w-4 h-4 mr-1.5" />
                {t('dashboard.series')}
              </Button>
            </Link>
            <Link to="/university/new">
              <Button variant="secondary" className="!border-indigo-300 !text-indigo-700 !bg-indigo-50 hover:!bg-indigo-100">
                <GraduationCap className="w-4 h-4 mr-1.5" />
                {t('dashboard.university')}
              </Button>
            </Link>
            <Link to="/course-tools">
              <Button variant="secondary" className="!border-teal-300 !text-teal-700 !bg-teal-50 hover:!bg-teal-100">
                <Wrench className="w-4 h-4 mr-1.5" />
                {t('dashboard.course_tools')}
              </Button>
            </Link>
            <Link to="/course-tools/library">
              <Button variant="secondary" className="!border-cyan-300 !text-cyan-700 !bg-cyan-50 hover:!bg-cyan-100">
                <Library className="w-4 h-4 mr-1.5" />
                {t('dashboard.course_library')}
              </Button>
            </Link>
            <Link to="/template-fill">
              <Button variant="secondary" className="!border-emerald-300 !text-emerald-700 !bg-emerald-50 hover:!bg-emerald-100">
                <FileEdit className="w-4 h-4 mr-1.5" />
                {t('dashboard.template_fill')}
              </Button>
            </Link>
            <Link to="/lesson/new">
              <Button>
                <Plus className="w-4 h-4 mr-1.5" />
                {t('dashboard.new')}
              </Button>
            </Link>
          </div>
        </div>

        {activeJobs.length > 0 && (
          <Link
            to="/course-tools/library"
            className="mb-6 flex items-center gap-3 rounded-xl border border-brand-200 bg-gradient-to-r from-brand-50 to-blue-50 px-4 py-3 hover:shadow-sm transition-all"
          >
            <Loader2 className="w-5 h-5 text-brand-600 animate-spin" />
            <div className="flex-1">
              <div className="text-sm font-medium text-brand-900">
                {t('tools.active_jobs_label').replace('{n}', String(activeJobs.length))}
              </div>
              <div className="text-xs text-brand-700 mt-0.5">
                {activeJobs.slice(0, 3).map((j) => j.title || t(`tools.tab_${j.tool_type}`)).join(' · ')}
                {activeJobs.length > 3 ? ' · ...' : ''}
              </div>
            </div>
            <div className="text-xs text-brand-600 font-medium">{t('tools.go_to_library')} →</div>
          </Link>
        )}

        {loading ? (
          <div className="text-center py-20">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto" />
            <p className="mt-3 text-gray-500 text-sm">{t('dashboard.loading')}</p>
          </div>
        ) : lessons.length === 0 ? (
          <div className="text-center py-20">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-600 mb-2">{t('dashboard.empty_title')}</h3>
            <p className="text-sm text-gray-400 mb-6">{t('dashboard.empty_desc')}</p>
            <div className="flex items-center justify-center gap-3">
              <Link to="/quick-generate">
                <Button variant="secondary" className="!border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100">
                  <Zap className="w-4 h-4 mr-1.5" />
                  {t('dashboard.quick')}
                </Button>
              </Link>
              <Link to="/lesson/new">
                <Button>
                  <Plus className="w-4 h-4 mr-1.5" />
                  {t('dashboard.new')}
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {lessons.map((l) => (
              <LessonCard key={l.id} lesson={l} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
