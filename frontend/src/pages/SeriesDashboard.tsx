import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { BookOpen, ArrowLeft, Play, Loader2, CheckCircle2, Clock, AlertCircle } from 'lucide-react'
import { useT } from '../i18n/translations'

interface SeriesData {
  id: string
  title: string
  subject: string
  grade_level: string
  total_weeks: number
  lessons_per_week: number
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
  status: string
}

interface SeriesLesson {
  id: string
  title: string
  status: string
  progress: number
  sequence_order: number
}

export default function SeriesDashboard() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const t = useT()
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [lessons, setLessons] = useState<SeriesLesson[]>([])
  const [generating, setGenerating] = useState(false)
  const [loading, setLoading] = useState(true)

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
        console.error('Load series failed:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [id])

  const handleGenerateAll = async () => {
    if (!id) return
    setGenerating(true)
    try {
      await api.post(`/api/v1/series/${id}/generate-all`)
      const lr = await api.get(`/api/v1/series/${id}/lessons`)
      setLessons(lr.data)
    } catch (e) {
      console.error('Generate all failed:', e)
    } finally {
      setGenerating(false)
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

  const totalLessons = series.total_weeks * series.lessons_per_week
  const completedLessons = lessons.filter((l) => l.status === 'completed').length

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => navigate('/dashboard')} className="text-gray-400 hover:text-gray-600">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <BookOpen className="w-6 h-6 text-brand-600" />
          <div>
            <h1 className="text-xl font-bold text-gray-900">{series.title}</h1>
            <p className="text-sm text-gray-500">
              {series.subject} · {series.grade_level} · {series.total_weeks}{t('series.week_label')} · {t('series.per_week')} {series.lessons_per_week} {t('series.total_lessons_unit')} · {t('series.total')} {totalLessons} {t('series.total_lessons_unit')}
            </p>
          </div>
        </div>

        {series.syllabus?.semester_overview && (
          <Card className="mb-6">
            <h2 className="font-semibold text-gray-900 mb-2">{t('series.overview')}</h2>
            <p className="text-sm text-gray-600 leading-relaxed">{series.syllabus.semester_overview}</p>
          </Card>
        )}

        {series.status === 'generating_syllabus' && (
          <Card className="mb-6">
            <div className="flex items-center gap-3 text-brand-600">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm font-medium">{t('series.generating_syllabus')}</span>
            </div>
          </Card>
        )}

        {series.status === 'syllabus_ready' && lessons.length === 0 && (
          <div className="mb-6">
            <Button onClick={handleGenerateAll} disabled={generating}>
              {generating ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Play className="w-4 h-4 mr-1.5" />}
              {t('series.start_generate')}
            </Button>
          </div>
        )}

        {lessons.length > 0 && (
          <Card className="mb-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-600">{t('series.progress')}</span>
              <span className="text-sm font-semibold text-brand-600">{completedLessons}/{lessons.length}</span>
            </div>
            <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-brand-500 h-2 rounded-full transition-all"
                style={{ width: `${lessons.length > 0 ? (completedLessons / lessons.length) * 100 : 0}%` }}
              />
            </div>
          </Card>
        )}

        {series.syllabus?.lessons && series.syllabus.lessons.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">{t('series.lesson_list')}</h2>
            {series.syllabus.lessons.map((item, idx) => {
              const lesson = lessons.find((l) => l.sequence_order === idx + 1)
              const statusColor = lesson?.status === 'completed' ? 'text-green-600 bg-green-50' :
                lesson?.status === 'processing' ? 'text-brand-600 bg-brand-50' :
                lesson?.status === 'failed' ? 'text-red-600 bg-red-50' :
                lesson?.status === 'queued' ? 'text-yellow-600 bg-yellow-50' : 'text-gray-400 bg-gray-50'

              const statusLabel =
                lesson?.status === 'completed' ? t('series.status_completed') :
                lesson?.status === 'processing' ? `${lesson.progress}%` :
                lesson?.status === 'failed' ? t('series.status_failed') :
                lesson?.status === 'queued' ? t('series.status_queued') :
                t('series.status_pending')

              return (
                <div key={idx} className="flex items-center gap-4 p-3 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
                  <span className="text-xs text-gray-400 w-16 flex-shrink-0">
                    第{item.week}周-{item.lesson_num}
                  </span>
                  <div className="flex-1 min-w-0">
                    {lesson ? (
                      <Link to={`/lesson/${lesson.id}/process`} className="text-sm font-medium text-gray-900 hover:text-brand-600 truncate block">
                        {item.title}
                      </Link>
                    ) : (
                      <span className="text-sm text-gray-700 truncate block">{item.title}</span>
                    )}
                    <p className="text-xs text-gray-500 truncate">{item.topic}</p>
                  </div>
                  <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${statusColor}`}>
                    {lesson?.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                    {lesson?.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                    {lesson?.status === 'failed' && <AlertCircle className="w-3 h-3" />}
                    {lesson?.status === 'queued' && <Clock className="w-3 h-3" />}
                    <span>{statusLabel}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}
