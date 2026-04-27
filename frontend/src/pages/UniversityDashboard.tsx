import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import PPTPanel from '../components/course/PPTPanel'
import SourcePicker, { SourceRef, applySourceToFormData } from '../components/course/SourcePicker'
import {
  GraduationCap, ArrowLeft, Play, Loader2, CheckCircle2, Clock, AlertCircle,
  Download, FileDown, Package, FileText, Sparkles,
} from 'lucide-react'
import { useT } from '../i18n/translations'

type TabKey = 'overview' | 'lessons' | 'exercises' | 'ppt' | 'export'

interface SeriesData {
  id: string
  title: string
  subject: string
  grade_level: string
  education_level?: string
  major?: string
  course_type?: string
  course_nature?: string
  total_weeks: number
  lessons_per_week: number
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
  status: string
}

interface SeriesLesson {
  id: string; title: string; status: string; progress: number; sequence_order: number
}

type ExType = 'in_class' | 'homework' | 'quiz' | 'project'
type ExDiff = 'easy' | 'medium' | 'hard' | 'mixed'
type ExMode = 'exercises' | 'practice'

export default function UniversityDashboard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const t = useT()
  const [tab, setTab] = useState<TabKey>('overview')
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [lessons, setLessons] = useState<SeriesLesson[]>([])
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!id) return
    const load = async () => {
      try {
        const [sr, lr] = await Promise.all([
          api.get(`/api/v1/series/${id}`),
          api.get(`/api/v1/series/${id}/lessons`),
        ])
        setSeries(sr.data)
        setLessons(lr.data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [id])

  const completedCount = lessons.filter(l => l.status === 'completed').length
  const totalExpected = series ? series.total_weeks * series.lessons_per_week : 0

  const handleGenerateAll = async () => {
    if (!id) return
    setGenerating(true)
    setErr('')
    try {
      await api.post(`/api/v1/series/${id}/generate-all`)
      const lr = await api.get(`/api/v1/series/${id}/lessons`)
      setLessons(lr.data)
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('university.generate_all_failed'))
    } finally {
      setGenerating(false)
    }
  }

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

  const tabs: { key: TabKey; label: string; icon: any }[] = [
    { key: 'overview', label: t('university.tab_overview'), icon: GraduationCap },
    { key: 'lessons', label: t('university.tab_lessons'), icon: FileText },
    { key: 'exercises', label: t('university.tab_exercises'), icon: Sparkles },
    { key: 'ppt', label: t('university.tab_ppt'), icon: Sparkles },
    { key: 'export', label: t('university.tab_export'), icon: Download },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <GraduationCap className="w-6 h-6 text-brand-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">{series.title}</h1>
            <p className="text-sm text-gray-500">
              {series.subject} · {series.major} · {series.grade_level} · {series.total_weeks}{t('series.week_label')} × {series.lessons_per_week}/{t('series.per_week')} = {totalExpected}
            </p>
          </div>
        </div>

        {err && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{err}</div>}

        <div className="flex gap-1 mb-6 border-b border-gray-200">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all ${
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
          <OverviewTab series={series} lessons={lessons} completedCount={completedCount}
            generating={generating} onGenerateAll={handleGenerateAll} t={t} navigate={navigate} />
        )}
        {tab === 'lessons' && (
          <LessonsTab series={series} lessons={lessons} navigate={navigate} t={t} />
        )}
        {tab === 'exercises' && (
          <ExercisesTab lessons={lessons} series={series} seriesId={id!} t={t} />
        )}
        {tab === 'ppt' && (
          <PPTTab lessons={lessons} series={series} seriesId={id!} t={t} />
        )}
        {tab === 'export' && (
          <ExportTab seriesId={id!} t={t} />
        )}
      </main>
    </div>
  )
}

function OverviewTab({ series, lessons, completedCount, generating, onGenerateAll, t, navigate }: any) {
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold text-gray-900 mb-3">{t('university.course_info')}</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="text-gray-500">{t('university.major_label')}:</span> <span className="text-gray-900">{series.major || '-'}</span></div>
          <div><span className="text-gray-500">{t('university.course_type_label')}:</span> <span className="text-gray-900">{series.course_type ? t(`university.course_type_${series.course_type}`) : '-'}</span></div>
          <div><span className="text-gray-500">{t('university.course_nature_label')}:</span> <span className="text-gray-900">{series.course_nature ? t(`university.course_nature_${series.course_nature}`) : '-'}</span></div>
          <div><span className="text-gray-500">{t('university.grade_label')}:</span> <span className="text-gray-900">{series.grade_level}</span></div>
        </div>
        {series.objectives && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="text-sm text-gray-500 mb-1">{t('university.objectives_label')}</div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.objectives}</div>
          </div>
        )}
        {series.special_requirements && (
          <div className="mt-3">
            <div className="text-sm text-gray-500 mb-1">{t('university.special_req_label')}</div>
            <div className="text-sm text-gray-800 whitespace-pre-wrap">{series.special_requirements}</div>
          </div>
        )}
      </Card>

      {series.syllabus?.semester_overview && (
        <Card>
          <h2 className="font-semibold text-gray-900 mb-2">{t('series.overview')}</h2>
          <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{series.syllabus.semester_overview}</p>
        </Card>
      )}

      {series.status === 'generating_syllabus' && (
        <Card>
          <div className="flex items-center gap-3 text-brand-600">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm font-medium">{t('series.generating_syllabus')}</span>
          </div>
        </Card>
      )}

      {series.status === 'syllabus_ready' && lessons.length === 0 && (
        <div>
          <Button onClick={onGenerateAll} disabled={generating}>
            {generating ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Play className="w-4 h-4 mr-1.5" />}
            {t('series.start_generate')}
          </Button>
        </div>
      )}

      {lessons.length > 0 && (
        <Card>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-600">{t('series.progress')}</span>
            <span className="text-sm font-semibold text-brand-600">{completedCount}/{lessons.length}</span>
          </div>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
            <div className="bg-brand-500 h-2 rounded-full transition-all"
              style={{ width: `${lessons.length > 0 ? (completedCount / lessons.length) * 100 : 0}%` }} />
          </div>
        </Card>
      )}
    </div>
  )
}

function LessonsTab({ series, lessons, navigate, t }: any) {
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
          <div key={idx} className="flex items-center gap-4 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
            <span className="text-xs text-gray-400 w-16 flex-shrink-0">
              {t('series.week_lesson').replace('{w}', String(item.week)).replace('{l}', String(item.lesson_num))}
            </span>
            <div className="flex-1 min-w-0">
              {lesson ? (
                <button onClick={() => navigate(`/lesson/${lesson.id}/process`)} className="text-sm font-medium text-gray-900 hover:text-brand-600 truncate block text-left">
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
          </div>
        )
      })}
    </div>
  )
}

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
          const { toast } = await import('../components/ui/Toast')
          const { useJobsStore } = await import('../stores/jobsStore')
          useJobsStore.getState().add({ result_id: rid, tool_type: mode as any, title: d.title || '' })
          toast.info(t('tools.job_enqueued'))
          const { getSocket } = await import('../services/socket')
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

function ExportTab({ seriesId, t }: any) {
  const [fmt, setFmt] = useState('docx')
  const [withEx, setWithEx] = useState(false)
  const [loading, setLoading] = useState<'merged' | 'zip' | ''>('')
  const [err, setErr] = useState('')

  const download = async (kind: 'merged' | 'zip') => {
    setLoading(kind)
    setErr('')
    try {
      const url = `/api/v1/series/${seriesId}/export-${kind}?format=${fmt}&include_exercises=${withEx}`
      const res = await api.get(url, { responseType: 'blob' })
      const blob = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const match = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = match ? decodeURIComponent(match[1].replace(/"/g, '')) :
        kind === 'zip' ? `series-${seriesId}.zip` : `series-${seriesId}.${fmt}`
      const a = document.createElement('a')
      a.href = blob
      a.download = fname
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blob)
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('university.export_failed'))
    } finally {
      setLoading('')
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold text-gray-900 mb-3">{t('university.export_title')}</h2>
        <p className="text-xs text-gray-500 mb-4">{t('university.export_hint')}</p>

        {err && <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">{err}</div>}

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-700 mb-1">{t('university.export_format')}</label>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
              <option value="docx">DOCX</option>
              <option value="pdf">PDF</option>
              <option value="md">Markdown</option>
              <option value="txt">TXT</option>
              <option value="json">JSON</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 mt-6">
            <input type="checkbox" checked={withEx} onChange={(e) => setWithEx(e.target.checked)} />
            {t('university.export_include_exercises')}
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => download('merged')} disabled={loading === 'merged'}
            className="p-4 rounded-xl border-2 border-gray-200 hover:border-brand-400 hover:bg-brand-50 transition-all text-left">
            <div className="flex items-center gap-2 mb-1">
              {loading === 'merged' ? <Loader2 className="w-4 h-4 animate-spin text-brand-600" /> : <FileDown className="w-4 h-4 text-brand-600" />}
              <span className="font-medium text-gray-900">{t('university.export_merged')}</span>
            </div>
            <p className="text-xs text-gray-500">{t('university.export_merged_desc')}</p>
          </button>
          <button onClick={() => download('zip')} disabled={loading === 'zip'}
            className="p-4 rounded-xl border-2 border-gray-200 hover:border-brand-400 hover:bg-brand-50 transition-all text-left">
            <div className="flex items-center gap-2 mb-1">
              {loading === 'zip' ? <Loader2 className="w-4 h-4 animate-spin text-brand-600" /> : <Package className="w-4 h-4 text-brand-600" />}
              <span className="font-medium text-gray-900">{t('university.export_zip')}</span>
            </div>
            <p className="text-xs text-gray-500">{t('university.export_zip_desc')}</p>
          </button>
        </div>
      </Card>
    </div>
  )
}
