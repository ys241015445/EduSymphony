import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useLessonStore, LessonSummary, SeriesSummary, LessonsScope } from '../stores/lessonStore'
import { useT } from '../i18n/translations'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { Plus, FileText, Clock, CheckCircle2, AlertCircle, Loader2, Trash2, Zap, BookOpen, Wrench, GraduationCap, FileEdit, Library, Zap as ZapIcon, Hourglass, Files, LayoutGrid, Layers, X, CalendarRange, NotebookPen } from 'lucide-react'
import { useJobsStore } from '../stores/jobsStore'
import { useAuthStore } from '../stores/authStore'
import { canUseCourseTools, parseAccessLevel, hasCapability } from '../lib/access'

/** Uniform height for dashboard toolbar buttons (primary + secondary). */
const DASH_BTN =
  '!h-10 !min-h-[2.5rem] !px-3 !py-0 text-sm shrink-0 whitespace-nowrap !gap-1.5'
const DASH_LINK = 'inline-flex'

const statusConfig: Record<string, { labelKey: string; color: string; icon: any }> = {
  queued: { labelKey: 'dashboard.status.queued', color: 'text-yellow-600 bg-yellow-50', icon: Clock },
  processing: { labelKey: 'dashboard.status.processing', color: 'text-blue-600 bg-blue-50', icon: Loader2 },
  awaiting_confirmation: { labelKey: 'dashboard.status.awaiting', color: 'text-amber-600 bg-amber-50', icon: Hourglass },
  completed: { labelKey: 'dashboard.status.completed', color: 'text-green-600 bg-green-50', icon: CheckCircle2 },
  quick_completed: { labelKey: 'dashboard.status.quick_completed', color: 'text-lime-700 bg-lime-50', icon: ZapIcon },
  failed: { labelKey: 'dashboard.status.failed', color: 'text-red-600 bg-red-50', icon: AlertCircle },
  draft: { labelKey: 'dashboard.status.draft', color: 'text-gray-600 bg-gray-50', icon: FileText },
}

function deriveDisplayStatus(lesson: LessonSummary): string {
  if (lesson.status === 'completed') {
    const isQuick = lesson.mode === 'quick' || (!lesson.has_stages && !lesson.has_full_optimized)
    if (isQuick) return 'quick_completed'
  }
  return lesson.status
}

function isUniversitySeries(s: SeriesSummary): boolean {
  return (s.education_level || '').toLowerCase() === 'university'
}

function seriesStatusLabelKey(status: string): string {
  switch (status) {
    case 'generating_syllabus':
      return 'series.generating_syllabus'
    case 'syllabus_ready':
      return 'dashboard.series_status.syllabus_ready'
    case 'generating':
      return 'series.status_processing'
    case 'completed':
      return 'series.status_completed'
    case 'error':
      return 'series.status_failed'
    case 'created':
      return 'dashboard.series_status.created'
    default:
      return 'dashboard.series_status.draft'
  }
}

function LessonCard({ lesson, scope }: { lesson: LessonSummary; scope?: LessonsScope }) {
  const t = useT()
  const navigate = useNavigate()
  const displayStatus = deriveDisplayStatus(lesson)
  const cfg = statusConfig[displayStatus] || statusConfig.draft
  const Icon = cfg.icon
  const isQuickCompleted = displayStatus === 'quick_completed'
  const qs = scope?.for_user_id ? `?for_user_id=${encodeURIComponent(scope.for_user_id)}` : ''

  const handleClick = () => {
    if (lesson.status === 'completed') {
      if (isQuickCompleted) {
        navigate(`/lesson/${lesson.id}/process${qs}`)
      } else {
        navigate(`/lesson/${lesson.id}/result${qs}`)
      }
    } else if (
      lesson.status === 'processing' ||
      lesson.status === 'queued' ||
      lesson.status === 'awaiting_confirmation'
    ) {
      navigate(`/lesson/${lesson.id}/process${qs}`)
    }
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (window.confirm(t('dashboard.confirm_delete'))) {
      const store = useLessonStore.getState()
      await store.deleteLesson(lesson.id, scope)
      store.fetchLessons(scope)
    }
  }

  return (
    <Card
      className="cursor-pointer hover:shadow-md hover:border-brand-200 transition-all duration-200 group h-full flex flex-col"
      padding={false}
    >
      <div onClick={handleClick} className="p-5 flex flex-col flex-1 min-h-[220px]">
        <div className="flex items-start justify-between mb-3 gap-2">
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium min-w-0 ${cfg.color}`}
            title={isQuickCompleted ? t('dashboard.quick_completed_hint') : undefined}
          >
            <Icon className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{t(cfg.labelKey)}</span>
          </div>
          <div className="w-9 h-9 shrink-0 flex items-start justify-end">
            <button
              type="button"
              onClick={handleDelete}
              className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 transition-all rounded-md"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
        <h3 className="font-semibold text-gray-900 mb-1 line-clamp-2 min-h-[2.5rem] leading-snug text-left">
          {lesson.title}
        </h3>
        <p className="text-sm text-gray-500 line-clamp-1">{lesson.subject} · {lesson.grade_level}</p>
        <div className="mt-3 h-[3.25rem] flex flex-col justify-start shrink-0">
          {lesson.status === 'processing' ? (
            <>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-full transition-all duration-500"
                  style={{ width: `${lesson.progress}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">{lesson.progress}%</p>
            </>
          ) : null}
        </div>
        <div className="mt-auto pt-3">
          {lesson.created_at ? (
            <p className="text-xs text-gray-400">
              {new Date(lesson.created_at).toLocaleDateString()}
            </p>
          ) : (
            <p className="text-xs text-transparent select-none" aria-hidden>—</p>
          )}
        </div>
      </div>
    </Card>
  )
}

function SeriesCard({ series, scope }: { series: SeriesSummary; scope?: LessonsScope }) {
  const t = useT()
  const navigate = useNavigate()
  const uni = isUniversitySeries(series)
  const statusKey = seriesStatusLabelKey(series.status)
  const borderClass = uni ? 'hover:border-indigo-300' : 'hover:border-violet-300'
  const badgeClass = uni
    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
    : 'bg-violet-50 text-violet-700 border-violet-200'
  const qs = scope?.for_user_id ? `?for_user_id=${encodeURIComponent(scope.for_user_id)}` : ''

  const handleClick = () => {
    navigate(`${uni ? `/university/${series.id}` : `/series/${series.id}`}${qs}`)
  }

  return (
    <Card
      className={`cursor-pointer hover:shadow-md ${borderClass} transition-all duration-200 h-full flex flex-col`}
      padding={false}
    >
      <div onClick={handleClick} className="p-5 flex flex-col flex-1 min-h-[220px]">
        <div className="flex items-start justify-between mb-3 gap-2">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border min-w-0 ${badgeClass}`}>
            {uni ? <GraduationCap className="w-3.5 h-3.5 shrink-0" /> : <Layers className="w-3.5 h-3.5 shrink-0" />}
            <span className="truncate">{uni ? t('dashboard.badge_university') : t('dashboard.badge_series')}</span>
          </div>
          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium text-gray-600 bg-gray-100 shrink-0 max-w-[40%]">
            <span className="truncate">{t(statusKey)}</span>
          </div>
        </div>
        <h3 className="font-semibold text-gray-900 mb-1 line-clamp-2 min-h-[2.5rem] leading-snug text-left">
          {series.title}
        </h3>
        <p className="text-sm text-gray-500 line-clamp-1">
          {series.subject} · {series.grade_level}
        </p>
        <p className="text-xs text-gray-400 mt-2 line-clamp-2 flex-1 min-h-[2.5rem]">
          {t('dashboard.series_card_sub').replace('{weeks}', String(series.total_weeks)).replace('{lpw}', String(series.lessons_per_week))}
        </p>
        <div className="mt-auto pt-3">
          {series.created_at ? (
            <p className="text-xs text-gray-400">
              {new Date(series.created_at).toLocaleDateString()}
            </p>
          ) : (
            <p className="text-xs text-transparent select-none" aria-hidden>—</p>
          )}
        </div>
      </div>
    </Card>
  )
}

type DashboardTab = 'all' | 'lessons' | 'series' | 'university'

export default function Dashboard() {
  const t = useT()
  const [searchParams, setSearchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || ''
  const lessonScope: LessonsScope | undefined = forUserId ? { for_user_id: forUserId } : undefined
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''

  const clearScopeFilter = () => {
    const p = new URLSearchParams(searchParams)
    p.delete('for_user_id')
    setSearchParams(p, { replace: true })
  }

  const user = useAuthStore((s) => s.user)
  const showCourseTools = canUseCourseTools(parseAccessLevel(user?.access_level)) && hasCapability(user as any, 'can_course_tools')
  const showTemplateFill = canUseCourseTools(parseAccessLevel(user?.access_level)) && hasCapability(user as any, 'can_template_fill')
  const showSeries = hasCapability(user as any, 'can_series')
  const showUniversity = hasCapability(user as any, 'can_university')
  const showSemesterHelper = hasCapability(user as any, 'can_semester_helper')
  const showZhukeMaterials = hasCapability(user as any, 'can_zhuke_materials')
  // 用原子 selector 单独订阅；store actions 不入 useEffect deps，避免触发循环
  const lessons       = useLessonStore((s) => s.lessons)
  const seriesList    = useLessonStore((s) => s.seriesList)
  const loading       = useLessonStore((s) => s.loading)
  const loadingSeries = useLessonStore((s) => s.loadingSeries)
  const jobs          = useJobsStore((s) => s.items)

  const [tab, setTab] = useState<DashboardTab>('all')

  useEffect(() => {
    const scope = forUserId ? { for_user_id: forUserId } : undefined
    useLessonStore.getState().fetchLessons(scope)
    useLessonStore.getState().fetchSeries(scope)
    useJobsStore.getState().bindSocket()
    useJobsStore.getState().refreshFromServer()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [forUserId])

  const activeJobs = jobs.filter((j) => j.status === 'queued' || j.status === 'running')

  const k12Series = useMemo(
    () => seriesList.filter((s) => !isUniversitySeries(s)),
    [seriesList],
  )
  const uniSeries = useMemo(
    () => seriesList.filter((s) => isUniversitySeries(s)),
    [seriesList],
  )

  const mergedAll = useMemo(() => {
    type Row = { kind: 'lesson'; id: string; ts: number; lesson: LessonSummary } | { kind: 'series'; id: string; ts: number; series: SeriesSummary }
    const rows: Row[] = []
    for (const l of lessons) {
      const ts = l.created_at ? new Date(l.created_at).getTime() : 0
      rows.push({ kind: 'lesson', id: `l-${l.id}`, ts, lesson: l })
    }
    for (const s of seriesList) {
      const ts = s.created_at ? new Date(s.created_at).getTime() : 0
      rows.push({ kind: 'series', id: `s-${s.id}`, ts, series: s })
    }
    rows.sort((a, b) => b.ts - a.ts)
    return rows
  }, [lessons, seriesList])

  const pageLoading = loading || loadingSeries

  const emptyMessage = (() => {
    if (tab === 'all') return t('dashboard.empty_all')
    if (tab === 'lessons') return t('dashboard.empty_lessons')
    if (tab === 'series') return t('dashboard.empty_series')
    return t('dashboard.empty_university')
  })()

  const isEmpty = (() => {
    if (tab === 'all') return mergedAll.length === 0
    if (tab === 'lessons') return lessons.length === 0
    if (tab === 'series') return k12Series.length === 0
    return uniSeries.length === 0
  })()

  const tabs: { key: DashboardTab; label: string; icon: any; count: number }[] = [
    { key: 'all', label: t('dashboard.tab_all'), icon: LayoutGrid, count: mergedAll.length },
    { key: 'lessons', label: t('dashboard.tab_lessons'), icon: FileText, count: lessons.length },
    { key: 'series', label: t('dashboard.tab_series'), icon: BookOpen, count: k12Series.length },
    { key: 'university', label: t('dashboard.tab_university'), icon: GraduationCap, count: uniSeries.length },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-8">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('dashboard.subtitle')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <Link to={`/quick-generate${scopeQs}`} className={DASH_LINK}>
              <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100`}>
                <Zap className="w-4 h-4 shrink-0" />
                {t('dashboard.quick')}
              </Button>
            </Link>
            {showSeries && (
              <Link to={`/series/new${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-violet-300 !text-violet-700 !bg-violet-50 hover:!bg-violet-100`}>
                  <BookOpen className="w-4 h-4 shrink-0" />
                  {t('dashboard.series')}
                </Button>
              </Link>
            )}
            {showUniversity && (
              <Link to={`/university/new${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-indigo-300 !text-indigo-700 !bg-indigo-50 hover:!bg-indigo-100`}>
                  <GraduationCap className="w-4 h-4 shrink-0" />
                  {t('dashboard.university')}
                </Button>
              </Link>
            )}
            {showCourseTools && (
              <>
                <Link to={`/course-tools${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-teal-300 !text-teal-700 !bg-teal-50 hover:!bg-teal-100`}>
                    <Wrench className="w-4 h-4 shrink-0" />
                    {t('dashboard.course_tools')}
                  </Button>
                </Link>
                <Link to={`/course-tools/library${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-cyan-300 !text-cyan-700 !bg-cyan-50 hover:!bg-cyan-100`}>
                    <Library className="w-4 h-4 shrink-0" />
                    {t('dashboard.course_library')}
                  </Button>
                </Link>
              </>
            )}
            <Link to={`/documents${scopeQs}`} className={DASH_LINK}>
              <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-pink-300 !text-pink-700 !bg-pink-50 hover:!bg-pink-100`}>
                <Files className="w-4 h-4 shrink-0" />
                {t('dashboard.documents')}
              </Button>
            </Link>
            {showTemplateFill && (
              <Link to={`/template-fill${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-emerald-300 !text-emerald-700 !bg-emerald-50 hover:!bg-emerald-100`}>
                  <FileEdit className="w-4 h-4 shrink-0" />
                  {t('dashboard.template_fill')}
                </Button>
              </Link>
            )}
            {showSemesterHelper && (
              <Link to={`/semester-helper${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100`}>
                  <CalendarRange className="w-4 h-4 shrink-0" />
                  {t('dashboard.semester_helper')}
                </Button>
              </Link>
            )}
            {showZhukeMaterials && (
              <Link to={`/zhuke-materials${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-sky-300 !text-sky-700 !bg-sky-50 hover:!bg-sky-100`}>
                  <NotebookPen className="w-4 h-4 shrink-0" />
                  {t('dashboard.zhuke_materials')}
                </Button>
              </Link>
            )}
            <Link to={`/lesson/new${scopeQs}`} className={DASH_LINK}>
              <Button size="sm" className={`${DASH_BTN} shadow-sm`}>
                <Plus className="w-4 h-4 shrink-0" />
                {t('dashboard.new')}
              </Button>
            </Link>
          </div>
        </div>

        {forUserId ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-950">
            <span>{t('admin.docs_scope_hint').replace('{id}', forUserId)}</span>
            <button
              type="button"
              onClick={clearScopeFilter}
              className="inline-flex items-center gap-1 text-amber-800 hover:text-amber-950 font-medium"
            >
              <X className="w-4 h-4" />
              {t('admin.clear_scope')}
            </button>
          </div>
        ) : null}

        {showCourseTools && activeJobs.length > 0 && (
          <Link
            to={`/course-tools/library${scopeQs}`}
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

        <div className="flex gap-1 mb-6 border-b border-gray-200 overflow-x-auto">
          {tabs.map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                tab === key
                  ? 'border-brand-500 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
              <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">{count}</span>
            </button>
          ))}
        </div>

        {pageLoading ? (
          <div className="text-center py-20">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin mx-auto" />
            <p className="mt-3 text-gray-500 text-sm">{t('dashboard.loading')}</p>
          </div>
        ) : isEmpty ? (
          <div className="text-center py-20">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-600 mb-2">{emptyMessage}</h3>
            <p className="text-sm text-gray-400 mb-6">{t('dashboard.empty_desc')}</p>
            <div className="flex flex-wrap items-center justify-center gap-2 max-w-3xl mx-auto">
              <Link to={`/quick-generate${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100`}>
                  <Zap className="w-4 h-4 shrink-0" />
                  {t('dashboard.quick')}
                </Button>
              </Link>
              {showSeries && (
                <Link to={`/series/new${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-violet-300 !text-violet-700 !bg-violet-50 hover:!bg-violet-100`}>
                    <BookOpen className="w-4 h-4 shrink-0" />
                    {t('dashboard.series')}
                  </Button>
                </Link>
              )}
              {showUniversity && (
                <Link to={`/university/new${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-indigo-300 !text-indigo-700 !bg-indigo-50 hover:!bg-indigo-100`}>
                    <GraduationCap className="w-4 h-4 shrink-0" />
                    {t('dashboard.university')}
                  </Button>
                </Link>
              )}
              {showCourseTools && (
                <>
                  <Link to={`/course-tools${scopeQs}`} className={DASH_LINK}>
                    <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-teal-300 !text-teal-700 !bg-teal-50 hover:!bg-teal-100`}>
                      <Wrench className="w-4 h-4 shrink-0" />
                      {t('dashboard.course_tools')}
                    </Button>
                  </Link>
                  <Link to={`/course-tools/library${scopeQs}`} className={DASH_LINK}>
                    <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-cyan-300 !text-cyan-700 !bg-cyan-50 hover:!bg-cyan-100`}>
                      <Library className="w-4 h-4 shrink-0" />
                      {t('dashboard.course_library')}
                    </Button>
                  </Link>
                </>
              )}
              <Link to={`/documents${scopeQs}`} className={DASH_LINK}>
                <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-pink-300 !text-pink-700 !bg-pink-50 hover:!bg-pink-100`}>
                  <Files className="w-4 h-4 shrink-0" />
                  {t('dashboard.documents')}
                </Button>
              </Link>
              {showTemplateFill && (
                <Link to={`/template-fill${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-emerald-300 !text-emerald-700 !bg-emerald-50 hover:!bg-emerald-100`}>
                    <FileEdit className="w-4 h-4 shrink-0" />
                    {t('dashboard.template_fill')}
                  </Button>
                </Link>
              )}
              {showSemesterHelper && (
                <Link to={`/semester-helper${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-amber-300 !text-amber-700 !bg-amber-50 hover:!bg-amber-100`}>
                    <CalendarRange className="w-4 h-4 shrink-0" />
                    {t('dashboard.semester_helper')}
                  </Button>
                </Link>
              )}
              {showZhukeMaterials && (
                <Link to={`/zhuke-materials${scopeQs}`} className={DASH_LINK}>
                  <Button variant="secondary" size="sm" className={`${DASH_BTN} !border-sky-300 !text-sky-700 !bg-sky-50 hover:!bg-sky-100`}>
                    <NotebookPen className="w-4 h-4 shrink-0" />
                    {t('dashboard.zhuke_materials')}
                  </Button>
                </Link>
              )}
              <Link to={`/lesson/new${scopeQs}`} className={DASH_LINK}>
                <Button size="sm" className={`${DASH_BTN} shadow-sm`}>
                  <Plus className="w-4 h-4 shrink-0" />
                  {t('dashboard.new')}
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 items-stretch">
            {tab === 'all' &&
              mergedAll.map((row) =>
                row.kind === 'lesson' ? (
                  <LessonCard key={row.id} lesson={row.lesson} scope={lessonScope} />
                ) : (
                  <SeriesCard key={row.id} series={row.series} scope={lessonScope} />
                ),
              )}
            {tab === 'lessons' && lessons.map((l) => <LessonCard key={l.id} lesson={l} scope={lessonScope} />)}
            {tab === 'series' && k12Series.map((s) => <SeriesCard key={s.id} series={s} scope={lessonScope} />)}
            {tab === 'university' && uniSeries.map((s) => <SeriesCard key={s.id} series={s} scope={lessonScope} />)}
          </div>
        )}
      </main>
    </div>
  )
}
