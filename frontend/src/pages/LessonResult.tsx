import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useLessonStore, LessonsScope } from '../stores/lessonStore'
import { api } from '../services/api'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { ArrowLeft, FileJson, FileText, Eye, BookOpen, Sparkles } from 'lucide-react'
import TeachingFeedback from '../components/lesson/TeachingFeedback'
import { useT } from '../i18n/translations'

type ViewMode = 'optimized' | 'draft' | 'stages'

export default function LessonResult() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const lessonScope = useMemo<LessonsScope | undefined>(
    () => (forUserId ? { for_user_id: forUserId } : undefined),
    [forUserId],
  )
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  const t = useT()
  const { currentLesson, fetchLesson } = useLessonStore()
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('optimized')

  useEffect(() => {
    if (id) fetchLesson(id, lessonScope)
  }, [id, forUserId, fetchLesson])

  // 仅在教案 id 变化（即载入一份新教案）时初始化默认 viewMode，
  // 避免用户在 stages 视图里点章节时被重置回 optimized 视图。
  useEffect(() => {
    const fc = currentLesson?.final_content
    if (!fc) return
    if (fc.full_optimized) {
      setViewMode('optimized')
    } else if (fc.full_draft) {
      setViewMode('draft')
    } else {
      setViewMode('stages')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLesson?.id])

  // 同理：仅在换到新教案时选中第一个章节，后续用户点哪个章节就显示哪个
  useEffect(() => {
    const fc = currentLesson?.final_content
    if (!fc?.stages) return
    const keys = Object.keys(fc.stages)
    if (keys.length > 0) setActiveStage(keys[0])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLesson?.id])

  if (!currentLesson) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto px-6 py-20 text-center text-gray-500">{t('result.loading')}</div>
      </div>
    )
  }

  const content = currentLesson.final_content
  const stages = content?.stages || {}
  const fullDraft = content?.full_draft || ''
  const fullOptimized = content?.full_optimized || ''

  const handleExport = async (format: string) => {
    try {
      let exportUrl = `/api/v1/export/${format}/${id}`
      if (forUserId) exportUrl += `?for_user_id=${encodeURIComponent(forUserId)}`
      const res = await api.get(exportUrl, { responseType: 'blob' })
      const blob = new Blob([res.data], {
        type: format === 'json' ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8',
      })
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      const safeName = (currentLesson.title || 'lesson_plan').replace(/[<>:"/\\|?*]/g, '_')
      a.download = `${safeName}.${format}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch (err: any) {
      const detail = err?.message?.trim?.() || ''
      const msg =
        err?.response?.status === 400
          ? t('result.export_not_ready')
          : err?.response?.status === 404
            ? t('result.export_not_found')
            : detail
              ? `${t('result.export_failed')}: ${detail}`
              : t('result.export_failed')
      alert(msg)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Top header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate(scopeQs ? `/dashboard${scopeQs}` : '/dashboard')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
              <ArrowLeft className="w-4 h-4" />
              {t('result.back')}
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{currentLesson.title}</h1>
              <p className="text-sm text-gray-500">
                {currentLesson.subject} · {currentLesson.grade_level}
                {content?.teaching_models ? ` · ${(content.teaching_models as string[]).join(' + ')}` : ''}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => handleExport('json')}>
              <FileJson className="w-4 h-4 mr-1.5" />
              JSON
            </Button>
            <Button variant="secondary" size="sm" onClick={() => handleExport('txt')}>
              <FileText className="w-4 h-4 mr-1.5" />
              TXT
            </Button>
            <Link to={`/lesson/${id}/process${scopeQs}`}>
              <Button variant="ghost" size="sm">
                <Eye className="w-4 h-4 mr-1.5" />
                {t('result.view_process')}
              </Button>
            </Link>
          </div>
        </div>

        {/* View mode tabs */}
        <div className="flex items-center gap-2 mb-6">
          {fullOptimized && (
            <button
              onClick={() => setViewMode('optimized')}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
                viewMode === 'optimized'
                  ? 'border-brand-300 bg-brand-50 text-brand-700 shadow-sm'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              {t('result.tab_optimized')}
            </button>
          )}
          {fullDraft && (
            <button
              onClick={() => setViewMode('draft')}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
                viewMode === 'draft'
                  ? 'border-brand-300 bg-brand-50 text-brand-700 shadow-sm'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              {t('result.tab_draft')}
            </button>
          )}
          <button
            onClick={() => setViewMode('stages')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
              viewMode === 'stages'
                ? 'border-brand-300 bg-brand-50 text-brand-700 shadow-sm'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <FileText className="w-4 h-4" />
            {t('result.tab_stages')}
          </button>
        </div>

        {/* Document view */}
        {viewMode === 'optimized' && fullOptimized && (
          <Card>
            <h2 className="text-lg font-semibold text-gray-900">{t('result.optimized_title')}</h2>
            <p className="text-sm text-gray-500 mt-1 mb-4">{t('process.optimized_desc')}</p>
            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {fullOptimized}
            </div>
          </Card>
        )}

        {viewMode === 'draft' && fullDraft && (
          <Card>
            <h2 className="text-lg font-semibold text-gray-900">{t('result.draft_title')}</h2>
            <p className="text-sm text-gray-500 mt-1 mb-4">{t('process.draft_desc')}</p>
            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {fullDraft}
            </div>
          </Card>
        )}

        {/* Per-stage view */}
        {viewMode === 'stages' && (
          <div className="grid lg:grid-cols-[240px_1fr] gap-6">
            <Card padding={false} className="h-fit sticky top-24">
              <div className="p-4">
                <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">{t('result.chapters')}</h3>
                <nav className="space-y-1">
                  {Object.entries(stages).map(([key, stage]: [string, any]) => (
                    <button
                      key={key}
                      onClick={() => setActiveStage(key)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        activeStage === key
                          ? 'bg-brand-50 text-brand-700 font-medium'
                          : 'text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      <span>{stage.model_name ? `${stage.model_name} - ${stage.stage_name}` : (stage.name || key)}</span>
                    </button>
                  ))}
                </nav>
              </div>
            </Card>

            <Card>
              {activeStage && stages[activeStage] ? (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-gray-900">{stages[activeStage].model_name ? `${stages[activeStage].model_name} - ${stages[activeStage].stage_name}` : (stages[activeStage].name || activeStage)}</h2>
                    {stages[activeStage].expert && (
                      <span className="text-xs text-gray-400 bg-gray-50 px-2.5 py-1 rounded-full">
                        {stages[activeStage].expert}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {stages[activeStage].content || stages[activeStage].draft || t('result.no_content')}
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-center py-10">{t('result.select_chapter')}</p>
              )}
            </Card>
          </div>
        )}

        {currentLesson && currentLesson.status === 'completed' && (
          <Card className="mt-6">
            <TeachingFeedback
              lessonId={currentLesson.id}
              lessonTitle={currentLesson.title}
              scopeQs={scopeQs}
              forUserId={forUserId}
            />
          </Card>
        )}
      </main>
    </div>
  )
}
