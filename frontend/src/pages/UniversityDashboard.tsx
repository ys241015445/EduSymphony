import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { getSocket, joinUser } from '../services/socket'
import { useAuthStore } from '../stores/authStore'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import PPTPanel from '../components/course/PPTPanel'
import SourcePicker, { SourceRef, applySourceToFormData } from '../components/course/SourcePicker'
import { toast } from '../components/ui/Toast'
import {
  GraduationCap, ArrowLeft, Loader2, CheckCircle2, Clock, AlertCircle,
  Download, FileText, Sparkles, RotateCcw, BookOpen, FileEdit,
} from 'lucide-react'
import { useT } from '../i18n/translations'
import { parseAccessLevel, isLimited } from '../lib/access'
import {
  useGenerationStats, GenerationStatusCard, SyllabusPreviewCard,
  MyDocsQuickAccessCard, ExportTab, ScheduleStat,
  type SharedSeriesLite, type SharedSeriesLesson,
} from '../components/series/SharedDashboardParts'

type TabKey = 'overview' | 'lessons' | 'exercises' | 'ppt' | 'export'

interface SeriesData extends SharedSeriesLite {
  subject: string
  grade_level: string
  education_level?: string
  major?: string
  course_type?: string
  course_nature?: string
  objectives?: string
  quality_goals?: string
  special_requirements?: string
  syllabus?: {
    semester_overview?: string
    lessons?: Array<{
      week: number; lesson_num: number; title: string; topic: string
      content_outline: string; objectives?: string
    }>
  }
}

type SeriesLesson = SharedSeriesLesson

type ExType = 'in_class' | 'homework' | 'quiz' | 'project'
type ExDiff = 'easy' | 'medium' | 'hard' | 'mixed'
type ExMode = 'exercises' | 'practice'

export default function UniversityDashboard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const seriesReadParams = forUserId ? { for_user_id: forUserId } : {}
  const dashBack = forUserId ? `/dashboard?for_user_id=${encodeURIComponent(forUserId)}` : '/dashboard'
  const t = useT()
  const userId = useAuthStore((s) => s.user?.id)
  const limitedUser = isLimited(parseAccessLevel(useAuthStore((s) => s.user?.access_level)))
  const [tab, setTab] = useState<TabKey>('overview')
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [lessons, setLessons] = useState<SeriesLesson[]>([])
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
      console.error(e)
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

  useEffect(() => {
    if (limitedUser && (tab === 'exercises' || tab === 'ppt')) {
      setTab('overview')
    }
  }, [limitedUser, tab])

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
    </div>
  )

  if (!series) return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8 text-center text-gray-500">
        {t('series.not_found')}
      </main>
    </div>
  )

  const tabsAll: { key: TabKey; label: string; icon: any }[] = [
    { key: 'overview', label: t('university.tab_overview'), icon: GraduationCap },
    { key: 'lessons', label: t('university.tab_lessons'), icon: FileText },
    { key: 'exercises', label: t('university.tab_exercises'), icon: Sparkles },
    { key: 'ppt', label: t('university.tab_ppt'), icon: Sparkles },
    { key: 'export', label: t('university.tab_export'), icon: Download },
  ]
  const tabs = limitedUser
    ? tabsAll.filter((x) => x.key !== 'exercises' && x.key !== 'ppt')
    : tabsAll

  const hasLessons = stats.totalExpected > 0 && (stats.completed + stats.processing + stats.queued + stats.failed) > 0

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate(dashBack)} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <GraduationCap className="w-6 h-6 text-brand-600" />
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900 truncate">{series.title}</h1>
            <p className="text-sm text-gray-500 truncate">
              {series.subject}
              {series.major ? ` · ${series.major}` : ''}
              {series.grade_level ? ` · ${series.grade_level}` : ''}
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
            <CourseInfoCard series={series} stats={stats} t={t} />
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
        {tab === 'exercises' && (
          <ExercisesTab lessons={lessons} series={series} seriesId={id!} t={t} />
        )}
        {tab === 'ppt' && (
          <PPTTab lessons={lessons} series={series} seriesId={id!} t={t} />
        )}
        {tab === 'export' && (
          <ExportTab seriesId={id!} stats={stats} navigate={navigate} forUserId={forUserId} t={t} />
        )}
      </main>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// CourseInfoCard
// ───────────────────────────────────────────────────────────────────
function CourseInfoCard({
  series, stats, t,
}: { series: SeriesData; stats: ReturnType<typeof useGenerationStats>; t: (k: string) => string }) {
  const items: { label: string; value: string | number }[] = [
    { label: t('university.major_label'), value: series.major || '-' },
    {
      label: t('university.course_type_label'),
      value: series.course_type ? t(`university.course_type_${series.course_type}`) : '-',
    },
    {
      label: t('university.course_nature_label'),
      value: series.course_nature ? t(`university.course_nature_${series.course_nature}`) : '-',
    },
    { label: t('university.grade_label'), value: series.grade_level || '-' },
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
        <ScheduleStat label={t('university.weeks_label')} value={series.total_weeks} unit={t('series.week_label')} />
        <ScheduleStat label={t('university.lessons_per_week')} value={series.lessons_per_week} unit={t('series.per_week')} />
        <ScheduleStat label={t('university.total_lessons_prefix')} value={stats.totalExpected} unit={t('university.total_lessons_unit')} highlight />
      </div>
      {series.objectives && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="text-sm text-gray-500 mb-1">{t('university.objectives_label')}</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.objectives}</div>
        </div>
      )}
      {series.quality_goals && (
        <div className="mt-3">
          <div className="text-sm text-gray-500 mb-1">{t('university.quality_goals_label')}</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.quality_goals}</div>
        </div>
      )}
      {series.special_requirements && (
        <div className="mt-3">
          <div className="text-sm text-gray-500 mb-1">{t('university.special_req_label')}</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.special_requirements}</div>
        </div>
      )}
    </Card>
  )
}

// ───────────────────────────────────────────────────────────────────
// LessonsTab
// ───────────────────────────────────────────────────────────────────
function LessonsTab({ series, lessons, navigate, forUserId, onRetryOne, onEditInDoc, t }: any) {
  const qs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  if (!series.syllabus?.lessons?.length) {
    return <Card><p className="text-sm text-gray-500">{t('university.no_syllabus_yet')}</p></Card>
  }
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

// ───────────────────────────────────────────────────────────────────
// ExercisesTab
// ───────────────────────────────────────────────────────────────────
function ExercisesTab({ lessons, series, seriesId, t }: any) {
  const completed = useMemo(() => lessons.filter((l: any) => l.status === 'completed'), [lessons])
  const [source, setSource] = useState<SourceRef | null>(null)
  const [mode, setMode] = useState<ExMode>('exercises')
  const [exType, setExType] = useState<ExType>('homework')
  const [difficulty, setDifficulty] = useState<ExDiff>('mixed')
  const [count, setCount] = useState(8)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [resultId, setResultId] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!source && completed.length) {
      setSource({ kind: 'lesson', id: completed[0].id, title: completed[0].title, mode: 'auto' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completed])

  const generate = async () => {
    if (!source) {
      setErr(t('university.pick_lesson_first'))
      return
    }
    setLoading(true)
    setErr('')
    setResult(null)
    try {
      const fd = new FormData()
      applySourceToFormData(fd, source)
      fd.append('subject', series.subject || '')
      fd.append('grade_level', series.grade_level || '')
      fd.append('provider', 'deepseek')
      if (mode === 'exercises') {
        fd.append('exercise_type', exType)
        fd.append('difficulty', difficulty)
        fd.append('count', String(count))
      } else {
        fd.append('practice_type', exType === 'homework' ? 'project' : 'in_class')
        fd.append('duration_min', '45')
      }
      const res = await api.post(`/api/v1/course-tools/${mode}`, fd)
      const d = res.data
      const rid = d.result_id || d.id
      setResultId(rid)
      if (d.status === 'queued') {
        setResult(null)
        try {
          const { useJobsStore } = await import('../stores/jobsStore')
          useJobsStore.getState().add({ result_id: rid, tool_type: mode as any, title: d.title || '' })
          toast.info(t('tools.job_enqueued'))
          const s = getSocket()
          const onDone = async (payload: any) => {
            if (payload?.result_id !== rid) return
            try {
              const r2 = await api.get(`/api/v1/course-tools/results/${rid}`)
              setResult(r2.data.result)
            } catch {}
            s.off('course_tool_completed', onDone)
          }
          s.on('course_tool_completed', onDone)
        } catch {}
      } else {
        setResult(d.result || null)
      }
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('university.gen_ex_failed'))
    } finally {
      setLoading(false)
    }
  }

  const download = async (fmt: string) => {
    if (!resultId) return
    try {
      const res = await api.get(`/api/v1/course-tools/${mode}/${resultId}/download?format=${fmt}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${mode}-${resultId}.${fmt}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('university.download_failed'))
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold text-gray-900 mb-3">{t('university.exercises_panel_title')}</h2>
        <p className="text-xs text-gray-500 mb-4">{t('university.exercises_panel_hint')}</p>

        {err && <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">{err}</div>}

        <div className="mb-3">
          <SourcePicker value={source} onChange={setSource} presetSeriesId={seriesId} />
        </div>

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-sm text-gray-700 mb-1">{t('university.ex_mode')}</label>
            <div className="flex gap-2">
              {(['exercises', 'practice'] as ExMode[]).map(v => (
                <button key={v} type="button" onClick={() => setMode(v)}
                  className={`flex-1 px-3 py-2 rounded-lg border text-sm ${
                    mode === v ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
                  }`}>
                  {t(`university.ex_mode_${v}`)}
                </button>
              ))}
            </div>
          </div>

          {mode === 'exercises' && (
            <>
              <div>
                <label className="block text-sm text-gray-700 mb-1">{t('university.ex_type')}</label>
                <select value={exType} onChange={(e) => setExType(e.target.value as ExType)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
                  <option value="in_class">{t('university.ex_type_in_class')}</option>
                  <option value="homework">{t('university.ex_type_homework')}</option>
                  <option value="quiz">{t('university.ex_type_quiz')}</option>
                  <option value="project">{t('university.ex_type_project')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">{t('university.ex_difficulty')}</label>
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as ExDiff)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
                  <option value="easy">{t('university.diff_easy')}</option>
                  <option value="medium">{t('university.diff_medium')}</option>
                  <option value="hard">{t('university.diff_hard')}</option>
                  <option value="mixed">{t('university.diff_mixed')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-1">{t('university.ex_count')}</label>
                <input type="number" min={1} max={20} value={count} onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm" />
              </div>
            </>
          )}
        </div>

        <Button onClick={generate} disabled={loading || !source} className="w-full">
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
          {t('university.generate_exercises')}
        </Button>
      </Card>

      {result && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-900">{result.title || t('university.exercises_result')}</h3>
            <div className="flex gap-2">
              {['docx', 'pdf', 'md', 'txt', 'json'].map(fmt => (
                <button key={fmt} onClick={() => download(fmt)}
                  className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50">
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded max-h-96 overflow-y-auto">
            {JSON.stringify(result, null, 2)}
          </pre>
        </Card>
      )}
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// PPTTab
// ───────────────────────────────────────────────────────────────────
function PPTTab({ lessons, series, seriesId, t }: any) {
  const completed = useMemo(() => lessons.filter((l: any) => l.status === 'completed'), [lessons])
  const [source, setSource] = useState<SourceRef | null>(null)

  useEffect(() => {
    if (!source && completed.length) {
      setSource({ kind: 'lesson', id: completed[0].id, title: completed[0].title, mode: 'auto' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [completed])

  const sourceLessonId = source?.kind === 'lesson' ? source.id : undefined
  const derivedTopic = sourceLessonId
    ? (lessons.find((l: any) => l.id === sourceLessonId)?.title || source?.title || '')
    : (source?.title || '')

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold text-gray-900 mb-3">{t('university.ppt_panel_title')}</h2>
        <div className="mb-3">
          <SourcePicker value={source} onChange={setSource} presetSeriesId={seriesId} />
        </div>

        {source ? (
          <PPTPanel
            sourceRef={source}
            subject={series.subject}
            gradeLevel={series.grade_level}
            topic={derivedTopic}
          />
        ) : (
          <p className="text-sm text-gray-500">{t('university.pick_lesson_hint')}</p>
        )}
      </Card>
    </div>
  )
}
