import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { getSocket, joinUser } from '../services/socket'
import { useAuthStore } from '../stores/authStore'
import Header from '../components/layout/Header'
import Card from '../components/ui/Card'
import { toast } from '../components/ui/Toast'
import {
  BookOpen, ArrowLeft, Loader2, CheckCircle2, Clock, AlertCircle,
  FileText, Download, RotateCcw, FileEdit,
} from 'lucide-react'
import { useT } from '../i18n/translations'
import {
  useGenerationStats, GenerationStatusCard, SyllabusPreviewCard,
  MyDocsQuickAccessCard, ExportTab, ScheduleStat,
  type SharedSeriesLite, type SharedSeriesLesson,
} from '../components/series/SharedDashboardParts'

type TabKey = 'overview' | 'lessons' | 'export'

interface SeriesData extends SharedSeriesLite {
  subject: string
  grade_level: string
  specific_grade?: string
  region?: string
  objectives?: string
  quality_goals?: string
  syllabus?: {
    semester_overview?: string
    lessons?: Array<{
      week: number
      lesson_num: number
      title: string
      topic: string
      content_outline: string
      objectives?: string
    }>
  }
}

export default function SeriesDashboard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const seriesReadParams = forUserId ? { for_user_id: forUserId } : {}
  const dashBack = forUserId ? `/dashboard?for_user_id=${encodeURIComponent(forUserId)}` : '/dashboard'
  const t = useT()
  const userId = useAuthStore((s) => s.user?.id)
  const [tab, setTab] = useState<TabKey>('overview')
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [lessons, setLessons] = useState<SharedSeriesLesson[]>([])
  const [enqueueing, setEnqueueing] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const stats = useGenerationStats(series, lessons)
  const allDoneRef = useRef(false)
  allDoneRef.current = stats.allDone

  const load = useCallback(async () => {
    if (!id) return
    try {
      const [sr, lr] = await Promise.all([
        api.get(`/api/v1/series/${id}`, { params: seriesReadParams }),
        api.get(`/api/v1/series/${id}/lessons`, { params: seriesReadParams }),
      ])
      setSeries(sr.data)
      setLessons(lr.data)
    } catch (e) {
      console.error('Load series failed:', e)
    } finally {
      setLoading(false)
    }
  }, [id, forUserId])

  useEffect(() => {
    if (!id) return
    load()
    if (userId) joinUser(userId)
    const socket = getSocket()

    const onProgress = (data: any) => {
      if (!data?.lesson_id) return
      setLessons(prev => prev.map(l =>
        l.id === data.lesson_id
          ? { ...l, status: data.status || l.status, progress: data.progress ?? l.progress }
          : l
      ))
    }
    const onCompleted = (data: any) => {
      if (!data?.lesson_id) return
      setLessons(prev => prev.map(l =>
        l.id === data.lesson_id ? { ...l, status: 'completed', progress: 100 } : l
      ))
      api.get(`/api/v1/series/${id}`, { params: seriesReadParams }).then(r => setSeries(r.data)).catch(() => {})
    }
    socket.on('progress_update', onProgress)
    socket.on('lesson_completed', onCompleted)

    const timer = setInterval(() => {
      if (allDoneRef.current) return
      load()
    }, 30000)

    return () => {
      socket.off('progress_update', onProgress)
      socket.off('lesson_completed', onCompleted)
      clearInterval(timer)
    }
  }, [id, userId, load, forUserId])

  const handleGenerateAll = async () => {
    if (!id) return
    setEnqueueing(true)
    setErr('')
    try {
      const res = await api.post(`/api/v1/series/${id}/generate-all`, null, {
        params: forUserId ? { for_user_id: forUserId } : undefined,
      })
      const total = res.data?.total ?? 0
      toast.success(t('university.batch_enqueued').replace('{n}', String(total)))
      await load()
    } catch (e: any) {
      const msg = e.response?.data?.detail || t('university.generate_all_failed')
      setErr(msg)
      toast.error(msg)
    } finally {
      setEnqueueing(false)
    }
  }

  const handleRetryFailed = async () => {
    const failedLessons = lessons.filter(l => l.status === 'failed')
    if (!failedLessons.length) return
    setRetrying(true)
    setErr('')
    let ok = 0
    for (const l of failedLessons) {
      try {
        await api.post(`/api/v1/lessons/${l.id}/regenerate-draft`, null, {
          params: forUserId ? { for_user_id: forUserId } : undefined,
        })
        ok += 1
      } catch (e) {
        // continue
      }
    }
    setRetrying(false)
    toast.success(t('university.retry_done').replace('{n}', String(ok)).replace('{total}', String(failedLessons.length)))
    await load()
  }

  const handleRetryOne = async (lessonId: string) => {
    try {
      await api.post(`/api/v1/lessons/${lessonId}/regenerate-draft`, null, {
        params: forUserId ? { for_user_id: forUserId } : undefined,
      })
      toast.success(t('university.retry_one_success'))
      setLessons(prev => prev.map(l => l.id === lessonId ? { ...l, status: 'queued', progress: 0 } : l))
    } catch (e: any) {
      toast.error(e.response?.data?.detail || t('university.retry_one_failed'))
    }
  }

  const handleEditInDoc = async (lessonId: string) => {
    try {
      const res = await api.post(
        `/api/v1/documents/lesson/${lessonId}/ensure-version`,
        null,
        { params: { source_kind: 'lesson_optimized', ...(forUserId ? { for_user_id: forUserId } : {}) } },
      )
      const vid = res.data?.version_id
      if (vid) {
        const p = new URLSearchParams()
        if (forUserId) p.set('for_user_id', forUserId)
        const qs = p.toString()
        navigate(qs ? `/documents/version/${vid}?${qs}` : `/documents/version/${vid}`)
      }
    } catch (e: any) {
      toast.error(e.response?.data?.detail || t('university.edit_in_doc_failed'))
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    )
  }

  if (!series) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <main className="max-w-4xl mx-auto px-6 py-8 text-center text-gray-500">{t('series.not_found')}</main>
      </div>
    )
  }

  const tabs: { key: TabKey; label: string; icon: any }[] = [
    { key: 'overview', label: t('university.tab_overview'), icon: BookOpen },
    { key: 'lessons', label: t('series.lesson_list'), icon: FileText },
    { key: 'export', label: t('university.tab_export'), icon: Download },
  ]

  const hasLessons = stats.totalExpected > 0 && (stats.completed + stats.processing + stats.queued + stats.failed) > 0

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate(dashBack)} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <BookOpen className="w-6 h-6 text-brand-600" />
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900 truncate">{series.title}</h1>
            <p className="text-sm text-gray-500 truncate">
              {series.subject}
              {series.grade_level ? ` · ${series.grade_level}` : ''}
              {series.specific_grade ? ` · ${series.specific_grade}` : ''}
              {` · ${series.total_weeks}${t('series.week_label')} × ${series.lessons_per_week}/${t('series.per_week')} = ${stats.totalExpected}`}
            </p>
          </div>
        </div>

        {err && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{err}</div>}

        <div className="flex gap-1 mb-6 border-b border-gray-200 overflow-x-auto">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                tab === key
                  ? 'border-brand-500 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon className="w-4 h-4" />{label}
            </button>
          ))}
        </div>

        {tab === 'overview' && (
          <div className="space-y-4">
            <BasicInfoCard series={series} stats={stats} t={t} />
            <GenerationStatusCard
              series={series}
              stats={stats}
              hasLessons={hasLessons}
              enqueueing={enqueueing}
              retrying={retrying}
              onGenerateAll={handleGenerateAll}
              onRetryFailed={handleRetryFailed}
              onGoExport={() => setTab('export')}
              t={t}
            />
            <MyDocsQuickAccessCard seriesId={series.id} completed={stats.completed} forUserId={forUserId} t={t} />
            <SyllabusPreviewCard
              semesterOverview={series.syllabus?.semester_overview}
              syllabus={series.syllabus?.lessons || []}
              lessons={lessons}
              onMore={() => setTab('lessons')}
              t={t}
            />
          </div>
        )}

        {tab === 'lessons' && (
          <LessonsTab
            series={series}
            lessons={lessons}
            navigate={navigate}
            forUserId={forUserId}
            onRetryOne={handleRetryOne}
            onEditInDoc={handleEditInDoc}
            t={t}
          />
        )}

        {tab === 'export' && (
          <ExportTab seriesId={id!} stats={stats} navigate={navigate} forUserId={forUserId} t={t} />
        )}
      </main>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// BasicInfoCard — K12 简化版
// ───────────────────────────────────────────────────────────────────
function BasicInfoCard({
  series, stats, t,
}: { series: SeriesData; stats: ReturnType<typeof useGenerationStats>; t: (k: string) => string }) {
  const items: { label: string; value: string }[] = [
    { label: t('series.subject_label'), value: series.subject || '-' },
    { label: t('series.grade_label'), value: series.grade_level || '-' },
    { label: t('series.specific_grade'), value: series.specific_grade || '-' },
    { label: t('series.region_label'), value: series.region || '-' },
  ]
  return (
    <Card>
      <h2 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <BookOpen className="w-5 h-5 text-brand-600" />
        {t('university.course_info')}
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {items.map((it) => (
          <div key={it.label} className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">{it.label}</div>
            <div className="text-sm font-medium text-gray-900 truncate">{it.value}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-3">
        <ScheduleStat label={t('series.total_weeks')} value={series.total_weeks} unit={t('series.week_label')} />
        <ScheduleStat label={t('series.lessons_per_week')} value={series.lessons_per_week} unit={t('series.per_week')} />
        <ScheduleStat label={t('series.total_lessons')} value={stats.totalExpected} unit={t('series.total_lessons_unit')} highlight />
      </div>
      {series.objectives && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="text-sm text-gray-500 mb-1">{t('series.objectives')}</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.objectives}</div>
        </div>
      )}
      {series.quality_goals && (
        <div className="mt-3">
          <div className="text-sm text-gray-500 mb-1">{t('series.quality_goals')}</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.quality_goals}</div>
        </div>
      )}
    </Card>
  )
}

// ───────────────────────────────────────────────────────────────────
// LessonsTab
// ───────────────────────────────────────────────────────────────────
function LessonsTab({ series, lessons, navigate, forUserId, onRetryOne, onEditInDoc, t }: any) {
  if (!series.syllabus?.lessons?.length) {
    return <Card><p className="text-sm text-gray-500">{t('university.no_syllabus_yet')}</p></Card>
  }
  const qs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  return (
    <div className="space-y-2">
      {series.syllabus.lessons.map((item: any, idx: number) => {
        const lesson = lessons.find((l: any) => l.sequence_order === idx + 1)
        const color = lesson?.status === 'completed' ? 'text-green-600 bg-green-50' :
          lesson?.status === 'processing' ? 'text-brand-600 bg-brand-50' :
          lesson?.status === 'failed' ? 'text-red-600 bg-red-50' :
          lesson?.status === 'queued' ? 'text-yellow-600 bg-yellow-50' : 'text-gray-400 bg-gray-50'
        const label =
          lesson?.status === 'completed' ? t('series.status_completed') :
          lesson?.status === 'processing' ? `${lesson.progress}%` :
          lesson?.status === 'failed' ? t('series.status_failed') :
          lesson?.status === 'queued' ? t('series.status_queued') : t('series.status_pending')
        return (
          <div key={idx} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
            <span className="text-xs text-gray-400 w-16 flex-shrink-0">
              {t('series.week_lesson').replace('{w}', String(item.week)).replace('{l}', String(item.lesson_num))}
            </span>
            <div className="flex-1 min-w-0">
              {lesson ? (
                <button onClick={() => navigate(`/lesson/${lesson.id}/process${qs}`)} className="text-sm font-medium text-gray-900 hover:text-brand-600 truncate block text-left">
                  {item.title}
                </button>
              ) : (
                <span className="text-sm text-gray-700 truncate block">{item.title}</span>
              )}
              <p className="text-xs text-gray-500 truncate">{item.topic}</p>
            </div>
            <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${color}`}>
              {lesson?.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
              {lesson?.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
              {lesson?.status === 'failed' && <AlertCircle className="w-3 h-3" />}
              {lesson?.status === 'queued' && <Clock className="w-3 h-3" />}
              <span>{label}</span>
            </div>
            {lesson?.status === 'completed' && (
              <button
                onClick={() => onEditInDoc(lesson.id)}
                title={t('university.edit_in_doc')}
                className="p-1.5 text-gray-400 hover:text-brand-600 transition-colors"
              >
                <FileEdit className="w-4 h-4" />
              </button>
            )}
            {lesson?.status === 'failed' && (
              <button
                onClick={() => onRetryOne(lesson.id)}
                title={t('university.retry_one')}
                className="p-1.5 text-gray-400 hover:text-brand-600 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
