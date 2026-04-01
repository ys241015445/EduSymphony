import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useLessonStore } from '../stores/lessonStore'
import { useAuthStore } from '../stores/authStore'
import { getSocket, joinLesson, leaveLesson } from '../services/socket'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import AgentCard from '../components/lesson/AgentCard'
import SectionPanel, { Section } from '../components/lesson/SectionPanel'
import VoteResult from '../components/lesson/VoteResult'
import AnnotationEditor from '../components/lesson/AnnotationEditor'
import { ArrowLeft, FileText, Loader2, CheckCircle2, Clock, RefreshCw, Download, ChevronDown, FileType, X, Eye, Printer, BookOpen } from 'lucide-react'
import StyledPdfModal from '../components/lesson/StyledPdfModal'
import { useMaterialGenStore } from '../stores/materialGenStore'

interface ActiveModel {
  key: string
  name: string
  reason: string
  stages: string[]
}

function buildAllSections(models?: ActiveModel[]): Section[] {
  if (!models || models.length === 0) return []
  const sections: Section[] = []
  for (const model of models) {
    for (let i = 0; i < model.stages.length; i++) {
      sections.push({
        key: `${model.key}_${i}`,
        name: model.stages[i],
        modelKey: model.key,
        modelName: model.name,
        status: 'pending' as const,
      })
    }
  }
  return sections
}

interface StreamBuffer {
  agentRole: string
  text: string
  phase: string
  provider?: string
  done: boolean
}

export default function LessonProcess() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const T = useT()
  const { currentLesson, fetchLesson, fetchDiscussions, discussions } = useLessonStore()

  const [sections, setSections] = useState<Section[]>([])
  const [activeSection, setActiveSection] = useState<string | null>(null)

  // Phase 0: Model recommendation
  const [modelRecText, setModelRecText] = useState('')
  const [modelRecStreaming, setModelRecStreaming] = useState(false)
  const [stageVotes, setStageVotes] = useState<Record<number, { accepted_role: string; pass_rate: number; agree?: number; disagree?: number }>>({})
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [isComplete, setIsComplete] = useState(false)
  const startTimeRef = useRef<number>(0)
  const centerPanelRef = useRef<HTMLDivElement>(null)

  const [streamBuffers, setStreamBuffers] = useState<Record<string, StreamBuffer>>({})
  const [streamingContent, setStreamingContent] = useState<Record<number, { text: string; done: boolean }>>({})

  // Full document states
  const [activeVersion, setActiveVersion] = useState<'draft' | 'optimized' | 'materials'>('draft')
  const [fullDraftText, setFullDraftText] = useState('')
  const [fullDraftStreaming, setFullDraftStreaming] = useState(false)
  const [fullOptimizedText, setFullOptimizedText] = useState('')
  const [fullOptimizedStreaming, setFullOptimizedStreaming] = useState(false)

  // Regenerating states
  const [regeneratingDiscussions, setRegeneratingDiscussions] = useState<Set<string>>(new Set())
  const [regeneratingDraft, setRegeneratingDraft] = useState(false)
  const [regeneratingOptimized, setRegeneratingOptimized] = useState(false)

  // Export dropdown
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)
  const exportMenuRef = useRef<HTMLDivElement>(null)

  // Model reason popover
  const [modelPopoverKey, setModelPopoverKey] = useState<string | null>(null)

  // Styled PDF modal + background task
  const [showStyledPdfModal, setShowStyledPdfModal] = useState(false)
  const [showStyledPdfResult, setShowStyledPdfResult] = useState(false)
  const [styledPdfDismissed, setStyledPdfDismissed] = useState(false)
  

  // Material generation background tasks (one per content version)
  const [previewingMaterial, setPreviewingMaterial] = useState<{ html: string; title: string; version: string } | null>(null)
  const startMaterialGen = useMaterialGenStore((s) => s.startGeneration)

  useEffect(() => {
    if (!id) return
    setFullDraftText('')
    setFullOptimizedText('')
    setFullDraftStreaming(false)
    setFullOptimizedStreaming(false)
    setSections([])
    setStreamBuffers({})
    setStreamingContent({})
    setStageVotes({})
    setActiveSection(null)
    setIsComplete(false)
    setActiveVersion('draft')
    setModelRecText('')
    setModelRecStreaming(false)
    fetchLesson(id)
    fetchDiscussions(id)
  }, [id, fetchLesson, fetchDiscussions])

  // Derive material & styled PDF states from currentLesson.final_content
  const fc = currentLesson?.final_content || {}
  const materialDraftTask = (() => {
    const status = fc.material_draft_status
    if (!status) return undefined
    return { status, html: fc.material_draft_html || '', error: fc.material_draft_error || '' }
  })()
  const materialOptimizedTask = (() => {
    const status = fc.material_optimized_status
    if (!status) return undefined
    return { status, html: fc.material_optimized_html || '', error: fc.material_optimized_error || '' }
  })()
  const styledPdfTask = (() => {
    const status = fc.styled_pdf_status
    if (!status) return undefined
    return {
      status,
      html: fc.styled_pdf_html || '',
      error: fc.styled_pdf_error || '',
      contentVersion: fc.styled_pdf_content_version || 'draft',
    }
  })()

  const anyBgGenerating = fc.material_draft_status === 'generating'
    || fc.material_optimized_status === 'generating'
    || fc.styled_pdf_status === 'generating'

  // Polling for state recovery (keep polling while lesson processing OR background tasks running)
  useEffect(() => {
    if (!id) return
    if (isComplete && !anyBgGenerating) return
    const interval = setInterval(() => {
      fetchLesson(id)
      if (!isComplete) fetchDiscussions(id)
    }, 3000)
    return () => clearInterval(interval)
  }, [id, isComplete, anyBgGenerating, fetchLesson, fetchDiscussions])

  // Derive active models from lesson data
  const activeModels: ActiveModel[] = (() => {
    const fc = currentLesson?.final_content
    return fc?.model_recommendation?.selected_models ?? []
  })()

  // Fill data from lesson.final_content (handles both complete and partial/streaming)
  useEffect(() => {
    if (!currentLesson) return
    const fc = currentLesson.final_content

    if (fc?.full_draft && !fullDraftStreaming) {
      setFullDraftText(fc.full_draft)
    }
    if (fc?.full_optimized && !fullOptimizedStreaming) {
      setFullOptimizedText(fc.full_optimized)
    }

    // Fallback: reconstruct from per-stage data if no full_draft
    if (!fc?.full_draft && fc?.stages && !fullDraftText) {
      const parts: string[] = []
      for (const key of Object.keys(fc.stages)) {
        const d = fc.stages[key]
        if (d?.draft) parts.push(`${d.model_name || ''} - ${d.stage_name || key}\n${d.draft}`)
      }
      if (parts.length > 0) setFullDraftText(parts.join('\n\n'))
    }

    if (!fc?.full_optimized && fc?.stages && !fullOptimizedText) {
      const parts: string[] = []
      for (const key of Object.keys(fc.stages)) {
        const d = fc.stages[key]
        if (d?.content) parts.push(`${d.model_name || ''} - ${d.stage_name || key}\n${d.content}`)
      }
      if (parts.length > 0) setFullOptimizedText(parts.join('\n\n'))
    }

    // Rebuild sections from Qwen-recommended models when model_recommendation is available
    const recModels: ActiveModel[] = fc?.model_recommendation?.selected_models ?? []
    if (recModels.length > 0) {
      setSections((prev) => {
        const freshSections = buildAllSections(recModels)
        const prevMap = new Map(prev.map((s) => [s.key, s]))
        return freshSections.map((s) => {
          const existing = prevMap.get(s.key)
          if (existing) return { ...s, status: existing.status, content: existing.content, expert: existing.expert }
          return s
        })
      })
    }

    // Update section statuses based on stored data + current_stage
    const currentStage = currentLesson.current_stage || 0
    const lessonStatus = currentLesson.status

    if (fc?.stages) {
      const finalStages = fc.stages as Record<string, any>
      setSections((prev) =>
        prev.map((s, idx) => {
          const d = finalStages[s.key]
          const stageNum = idx + 1

          if (d?.content) {
            return { ...s, status: 'done' as const, content: d.content, expert: d.expert }
          }

          if (lessonStatus === 'completed') {
            return { ...s, status: 'done' as const }
          }

          if (lessonStatus === 'processing' && currentStage > 0) {
            if (stageNum === currentStage) {
              return { ...s, status: 'processing' as const }
            }
            if (stageNum < currentStage) {
              return { ...s, status: 'done' as const }
            }
          }

          return { ...s, status: s.status === 'processing' ? 'processing' : 'pending' as const }
        })
      )
    } else if (lessonStatus === 'processing' && !fc?.stages) {
      setSections((prev) => prev.map((s) => ({ ...s, status: 'pending' as const })))
    }

    if (lessonStatus === 'completed') {
      setIsComplete(true)
    }
  }, [currentLesson])

  // Socket.IO real-time updates
  useEffect(() => {
    if (!id) return
    const socket = getSocket()
    joinLesson(id)
    console.log('[LessonProcess] Socket connected, joined room for', id)

    socket.on('progress_update', (data: any) => {
      if (data.lesson_id !== id) return

      if (data.stage === 'started' && !startTimeRef.current) {
        startTimeRef.current = Date.now()
      }

      if (data.stage === 'awaiting_confirmation') {
        fetchLesson(id!)
      }

      if (data.stage === 'section_start') {
        const sectionKey = data.section_key || ''
        setSections((prev) => prev.map((s) =>
          s.key === sectionKey ? { ...s, status: 'processing' } : s
        ))
        setActiveSection(sectionKey)
      }

      if (data.stage === 'section_done') {
        const sectionKey = data.section_key || ''
        setSections((prev) => prev.map((s) =>
          s.key === sectionKey
            ? { ...s, status: 'done', content: data.content_preview }
            : s
        ))
      }
    })

    socket.on('stream_start', (data: any) => {
      if (data.lesson_id !== id) return
      console.log('[LessonProcess] stream_start', data.phase, data.agent_role)

      if (data.phase === 'model_recommendation') {
        setModelRecText('')
        setModelRecStreaming(true)
      } else if (data.phase === 'full_draft') {
        setFullDraftStreaming(true)
        setFullDraftText('')
        setActiveVersion('draft')
      } else if (data.phase === 'full_optimized') {
        setFullOptimizedStreaming(true)
        setFullOptimizedText('')
        setActiveVersion('optimized')
      } else if (data.phase === 'finalize') {
        setStreamingContent((prev) => ({
          ...prev,
          [data.stage]: { text: '', done: false },
        }))
      } else {
        const key = `${data.stage}_${data.agent_role}`
        setStreamBuffers((prev) => ({
          ...prev,
          [key]: {
            agentRole: data.agent_role,
            text: '',
            phase: data.phase,
            provider: data.provider,
            done: false,
          },
        }))
      }
    })

    socket.on('stream_chunk', (data: any) => {
      if (data.lesson_id !== id) return

      if (data.phase === 'model_recommendation') {
        setModelRecText((prev) => prev + data.chunk)
      } else if (data.phase === 'full_draft') {
        setFullDraftText((prev) => prev + data.chunk)
      } else if (data.phase === 'full_optimized') {
        setFullOptimizedText((prev) => prev + data.chunk)
      } else if (data.phase === 'finalize') {
        setStreamingContent((prev) => {
          const current = prev[data.stage] || { text: '', done: false }
          return { ...prev, [data.stage]: { ...current, text: current.text + data.chunk } }
        })
      } else {
        const key = `${data.stage}_${data.agent_role}`
        setStreamBuffers((prev) => {
          const current = prev[key]
          if (!current) return prev
          return { ...prev, [key]: { ...current, text: current.text + data.chunk } }
        })
      }
    })

    socket.on('stream_end', (data: any) => {
      if (data.lesson_id !== id) return
      console.log('[LessonProcess] stream_end', data.phase, data.agent_role)

      if (data.phase === 'model_recommendation') {
        setModelRecStreaming(false)
        fetchLesson(id)
      } else if (data.phase === 'full_draft') {
        setFullDraftText(data.full_text || '')
        setFullDraftStreaming(false)
      } else if (data.phase === 'full_optimized') {
        setFullOptimizedText(data.full_text || '')
        setFullOptimizedStreaming(false)
      } else if (data.phase === 'finalize') {
        setStreamingContent((prev) => ({
          ...prev,
          [data.stage]: { text: data.full_text || prev[data.stage]?.text || '', done: true },
        }))
      } else {
        const key = `${data.stage}_${data.agent_role}`
        setStreamBuffers((prev) => {
          const current = prev[key]
          if (!current) return prev
          return {
            ...prev,
            [key]: { ...current, text: data.full_text || current.text, done: true },
          }
        })
      }
    })

    socket.on('all_drafts_ready', (data: any) => {
      if (data.lesson_id !== id) return
      fetchLesson(id)
    })

    socket.on('discussion_update', (data: any) => {
      if (data.lesson_id !== id) return
      if (data.type === 'vote_complete') {
        setStageVotes((prev) => ({
          ...prev,
          [data.stage]: {
            accepted_role: data.accepted_role,
            pass_rate: data.pass_rate,
            agree: data.agree,
            disagree: data.disagree,
          },
        }))
      }
    })

    socket.on('lesson_completed', (data: any) => {
      if (data.lesson_id !== id) return
      setIsComplete(true)
      fetchLesson(id)
      fetchDiscussions(id)
    })

    socket.on('stage_regenerated', (data: any) => {
      if (data.lesson_id !== id) return
      fetchLesson(id)
    })

    socket.on('votes_saved', (data: any) => {
      if (data.lesson_id !== id) return
      fetchDiscussions(id)
    })

    socket.on('bg_task_complete', (data: any) => {
      if (data.lesson_id !== id) return
      fetchLesson(id)
    })

    return () => {
      leaveLesson(id)
      socket.off('progress_update')
      socket.off('stream_start')
      socket.off('stream_chunk')
      socket.off('stream_end')
      socket.off('all_drafts_ready')
      socket.off('discussion_update')
      socket.off('lesson_completed')
      socket.off('stage_regenerated')
      socket.off('votes_saved')
      socket.off('bg_task_complete')
    }
  }, [id, fetchLesson, fetchDiscussions])

  useEffect(() => {
    if (!currentLesson?.started_at) return
    const toUtc = (ts: string) => ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z'
    const start = new Date(toUtc(currentLesson.started_at)).getTime()
    startTimeRef.current = start
    if (isComplete && currentLesson.completed_at) {
      const end = new Date(toUtc(currentLesson.completed_at)).getTime()
      setElapsedSeconds(Math.floor((end - start) / 1000))
      return
    }
    setElapsedSeconds(Math.floor((Date.now() - start) / 1000))
  }, [currentLesson?.started_at, currentLesson?.completed_at, isComplete])

  useEffect(() => {
    if (isComplete || !startTimeRef.current) return
    const timer = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [isComplete, currentLesson?.started_at])

  // Auto-scroll center panel
  useEffect(() => {
    if (centerPanelRef.current && (fullDraftStreaming || fullOptimizedStreaming)) {
      centerPanelRef.current.scrollTop = centerPanelRef.current.scrollHeight
    }
  }, [fullDraftText, fullOptimizedText, fullDraftStreaming, fullOptimizedStreaming])

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}m ${sec.toString().padStart(2, '0')}s`
  }

  const handleRegenerateDiscussion = async (discussionId: string) => {
    if (!id) return
    setRegeneratingDiscussions((prev) => new Set(prev).add(discussionId))

    // Find which section this discussion belongs to and mark it as processing
    const disc = discussions.find((d) => d.id === discussionId)
    if (disc) {
      const sectionIdx = disc.stage - 1
      setSections((prev) => prev.map((s, i) =>
        i === sectionIdx ? { ...s, status: 'processing' as const } : s
      ))
    }

    try {
      await api.post(`/api/v1/lessons/${id}/discussions/${discussionId}/regenerate`)
      await fetchDiscussions(id)
    } catch (e) {
      console.error('Regenerate discussion failed:', e)
    } finally {
      setRegeneratingDiscussions((prev) => {
        const next = new Set(prev)
        next.delete(discussionId)
        return next
      })
      // Restore the section to done after regeneration completes
      if (disc) {
        const sectionIdx = disc.stage - 1
        setSections((prev) => prev.map((s, i) =>
          i === sectionIdx ? { ...s, status: 'done' as const } : s
        ))
      }
    }
  }

  const handleRegenerateDraft = async () => {
    if (!id || regeneratingDraft) return
    if (!confirm(T('process.confirm_regen_draft'))) return
    setRegeneratingDraft(true)
    setIsComplete(false)
    setFullDraftText('')
    setFullOptimizedText('')
    setSections(buildAllSections())
    setStreamBuffers({})
    setStreamingContent({})
    setStageVotes({})
    setActiveVersion('draft')
    try {
      await api.post(`/api/v1/lessons/${id}/regenerate-draft`)
    } catch (e) {
      console.error('Regenerate draft failed:', e)
      alert(T('process.regen_failed'))
    } finally {
      setRegeneratingDraft(false)
    }
  }

  const handleRegenerateOptimized = async () => {
    if (!id || regeneratingOptimized) return
    setRegeneratingOptimized(true)
    setIsComplete(false)
    setFullOptimizedText('')
    setActiveVersion('optimized')
    try {
      await api.post(`/api/v1/lessons/${id}/regenerate-optimized`)
    } catch (e) {
      console.error('Regenerate optimized failed:', e)
      alert(T('process.optimize_failed'))
    } finally {
      setRegeneratingOptimized(false)
    }
  }

  // Close export menu when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false)
      }
    }
    if (showExportMenu) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showExportMenu])

  const EXPORT_FORMATS = [
    { key: 'json', label: 'JSON', icon: '{ }', mime: 'application/json' },
    { key: 'txt', label: T('process.export_txt'), icon: 'Aa', mime: 'text/plain' },
    { key: 'markdown', label: 'Markdown', icon: 'Md', mime: 'text/markdown' },
    { key: 'docx', label: T('process.export_word'), icon: 'W', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
    { key: 'pdf', label: T('process.export_pdf'), icon: 'Pdf', mime: 'application/pdf' },
  ]

  const handleExport = async (format: string) => {
    if (!id) return
    setExporting(format)
    setShowExportMenu(false)
    try {
      const token = useAuthStore.getState().token
      const res = await fetch(`/api/v1/export/${format}/${id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || T('process.export_failed'))
      }
      const blob = await res.blob()
      const ext = format === 'markdown' ? 'md' : format
      const safeName = (currentLesson?.title || 'lesson_plan').replace(/[<>:"/\\|?*]/g, '_')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeName}.${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: any) {
      console.error('Export failed:', e)
      alert(e.message || T('process.export_failed'))
    } finally {
      setExporting(null)
    }
  }

  const activeSectionIdx = sections.findIndex((s) => s.key === activeSection)
  const activeStageNum = activeSectionIdx >= 0 ? activeSectionIdx + 1 : 0

  const sectionDiscussions = discussions.filter((d) => d.stage === activeStageNum)

  const activeAnalysisStreams = Object.entries(streamBuffers)
    .filter(([key, buf]) => key.startsWith(`${activeStageNum}_`) && buf.phase === 'analysis')
    .map(([, buf]) => buf)

  const expertVoteStreams = Object.entries(streamBuffers)
    .filter(([key, buf]) => key.startsWith(`${activeStageNum}_`) && buf.phase === 'expert_vote')
    .map(([, buf]) => buf)

  const voteResultStream = Object.entries(streamBuffers)
    .filter(([key, buf]) => key.startsWith(`${activeStageNum}_`) && buf.phase === 'vote_result')
    .map(([, buf]) => buf)[0]

  const finalizeStream = streamingContent[activeStageNum]

  const totalSections = sections.length
  const doneSections = sections.filter((s) => s.status === 'done').length

  const activeDocText = activeVersion === 'draft' ? fullDraftText : activeVersion === 'optimized' ? fullOptimizedText : ''
  const activeDocStreaming = activeVersion === 'draft' ? fullDraftStreaming : activeVersion === 'optimized' ? fullOptimizedStreaming : false
  const anyMaterialGenerating = fc.material_draft_status === 'generating' || fc.material_optimized_status === 'generating'

  const draftStatus = fullDraftStreaming ? 'streaming' : fullDraftText ? 'done' : 'pending'
  const optimizedStatus = fullOptimizedStreaming ? 'streaming' : fullOptimizedText ? 'done' : 'pending'

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Top bar — fixed height, never scrolls */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 z-50">
        <div className="max-w-[1800px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/dashboard')} className="text-gray-400 hover:text-gray-600 transition-colors">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-600" />
              <span className="font-semibold text-gray-900 text-sm">
                {currentLesson?.title || T('process.generating')}
              </span>
            </div>
            {activeModels.length > 0 && (
              <div className="flex items-center gap-1.5 ml-4 relative">
                {activeModels.map((m, i) => (
                  <div key={m.key} className="relative">
                    <button
                      onClick={() => setModelPopoverKey(modelPopoverKey === m.key ? null : m.key)}
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded cursor-pointer transition-colors ${MODEL_BADGE_COLORS[i % MODEL_BADGE_COLORS.length]}`}
                    >
                      {m.name}
                    </button>
                    {modelPopoverKey === m.key && (
                      <div className="absolute top-full left-0 mt-1.5 w-64 bg-white rounded-lg border border-gray-200 shadow-xl z-[60] p-3">
                        <div className="flex items-center justify-between mb-2">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${MODEL_BADGE_COLORS[i % MODEL_BADGE_COLORS.length]}`}>{m.name}</span>
                          <button onClick={() => setModelPopoverKey(null)} className="text-gray-400 hover:text-gray-600">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{m.reason || T('process.default_reason')}</p>
                        {m.stages && m.stages.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {m.stages.map((s) => (
                              <span key={s} className="text-[9px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{s}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="text-gray-500 font-mono">{formatElapsed(elapsedSeconds)}</span>
            </div>
            {isComplete ? (
              <Link to={`/lesson/${id}/result`}>
                <Button size="sm">
                  <CheckCircle2 className="w-4 h-4 mr-1.5" />
                  {T('process.view_result')}
                </Button>
              </Link>
            ) : currentLesson?.status === 'awaiting_confirmation' ? (
              <Button size="sm" onClick={async () => {
                if (!id) return
                try {
                  await api.post(`/api/v1/lessons/${id}/confirm-step`)
                  fetchLesson(id)
                } catch (e) { console.error('Confirm step failed:', e) }
              }}>
                <CheckCircle2 className="w-4 h-4 mr-1.5" />
                {T('process.confirm_continue')}
              </Button>
            ) : (
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />
                <span className="text-sm text-brand-600 font-medium">{T('process.generating_status')}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main content: 2 columns — takes all remaining height */}
      <div className="flex-1 flex min-h-0">
        {/* LEFT COLUMN: Lesson info + section nav + AI discussion (merged) */}
        <div className="w-[420px] flex-shrink-0 border-r border-gray-200 panel-scroll bg-white">
          <div className="p-4">
            {/* Lesson info */}
            <div className="mb-4">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">{T('process.lesson_info')}</h3>
              <h2 className="text-sm font-bold text-gray-900 mb-1">{currentLesson?.title}</h2>
              <p className="text-xs text-gray-500">
                {currentLesson?.subject} · {currentLesson?.grade_level}
                {currentLesson?.topic ? ` · ${currentLesson.topic}` : ''}
              </p>
            </div>

            {/* Model Recommendation Card */}
            {(modelRecStreaming || modelRecText || activeModels.length > 0) && (
              <ModelRecommendationCard
                streamingText={modelRecText}
                isStreaming={modelRecStreaming}
                models={activeModels}
                overallReason={currentLesson?.final_content?.model_recommendation?.overall_reason}
                T={T}
              />
            )}

            {/* Section nav */}
            <div className="mb-4">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">{T('process.sections')}</h3>
              <SectionPanel
                sections={sections}
                activeKey={activeSection}
                onSelect={setActiveSection}
              />
            </div>

            {/* AI Discussion (merged from old right column) */}
            <div className="border-t border-gray-200 pt-4">
              <div className="flex items-center gap-4 mb-4 pb-3 border-b border-gray-100">
                <div className="text-xs text-gray-400 uppercase tracking-wider">
                  {T('process.sections')} {doneSections}/{totalSections}
                </div>
                {isComplete && (
                  <span className="ml-auto text-xs font-semibold text-green-600 bg-green-50 px-2.5 py-1 rounded-full">
                    {T('process.completed')}
                  </span>
                )}
              </div>

              {activeSection ? (
                <div className="space-y-6">
                  {/* Expert analysis */}
                  <div>
                    <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">
                      {T('process.expert_analysis')}
                    </h3>
                    {sections[activeSectionIdx] && (
                      <p className="text-xs text-gray-600 mb-3 font-medium">
                        {sections[activeSectionIdx].modelName} — {sections[activeSectionIdx].name}
                      </p>
                    )}
                    <div className="space-y-3">
                      {activeAnalysisStreams.length > 0 && activeAnalysisStreams.map((buf) => (
                        <AgentCard
                          key={`stream-${activeStageNum}-${buf.agentRole}`}
                          role={buf.agentRole}
                          streamingText={buf.text}
                          isStreaming={!buf.done}
                          provider={buf.provider}
                        />
                      ))}

                      {activeAnalysisStreams.length === 0 && sectionDiscussions.map((d) => (
                        <AgentCard
                          key={d.id}
                          role={d.agent_role}
                          opinion={d.opinion}
                          isAccepted={d.is_accepted}
                          votes={d.votes || null}
                          timestamp={d.created_at ? new Date(d.created_at).toLocaleTimeString('zh-CN', { hour12: false }) : undefined}
                          onRegenerate={() => handleRegenerateDiscussion(d.id)}
                          isRegenerating={regeneratingDiscussions.has(d.id)}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Expert Voting */}
                  {expertVoteStreams.length > 0 && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                        {T('process.expert_vote')}
                      </h3>
                      <div className="space-y-3">
                        {expertVoteStreams.map((buf) => (
                          <AgentCard
                            key={`vote-${activeStageNum}-${buf.agentRole}`}
                            role={buf.agentRole}
                            streamingText={buf.text}
                            isStreaming={!buf.done}
                            provider={buf.provider}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Vote Result */}
                  {(voteResultStream || stageVotes[activeStageNum] || (isComplete && sectionDiscussions.some((d) => d.is_accepted))) && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                        {T('process.vote_discussion')}
                      </h3>
                      {voteResultStream && (
                        <AgentCard
                          key={`voteresult-${activeStageNum}`}
                          role="教研主持人"
                          streamingText={voteResultStream.text}
                          isStreaming={!voteResultStream.done}
                        />
                      )}
                      {stageVotes[activeStageNum] && (
                        <div className="mt-3">
                          <VoteResult
                            agree={stageVotes[activeStageNum].agree || 3}
                            disagree={stageVotes[activeStageNum].disagree || 2}
                            acceptedRole={stageVotes[activeStageNum].accepted_role}
                            passRate={stageVotes[activeStageNum].pass_rate}
                          />
                        </div>
                      )}
                      {isComplete && !stageVotes[activeStageNum] && sectionDiscussions.some((d) => d.is_accepted) && (
                        <div className="mt-3">
                          {sectionDiscussions.filter((d) => d.is_accepted).map((d) => {
                            const summary = d.votes?.summary || d.votes || {}
                            return (
                              <VoteResult
                                key={d.id}
                                agree={summary.agree || 0}
                                disagree={summary.disagree || 0}
                                acceptedRole={d.agent_role}
                                passRate={d.pass_rate || 0}
                              />
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Finalize streaming */}
                  {finalizeStream && (
                    <div>
                      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
                        {T('process.lesson_gen')}
                      </h3>
                      <AgentCard
                        key={`finalize-${activeStageNum}`}
                        role="教案编写专家"
                        streamingText={finalizeStream.text}
                        isStreaming={!finalizeStream.done}
                      />
                    </div>
                  )}

                  {/* Annotation */}
                  {sections[activeSectionIdx]?.status === 'done' && (
                    <div className="pt-3 border-t border-gray-100">
                      <AnnotationEditor
                        lessonId={id!}
                        sectionKey={activeSection}
                        onSubmitted={() => fetchLesson(id!)}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-gray-400">
                  <FileText className="w-6 h-6 mb-2" />
                  <span className="text-xs">{T('process.select_section')}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Version tabs at top + Full document view */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
          {/* Version tabs bar (sticky at top of center column) */}
          <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-3">
            <div className="flex items-center gap-3">
              <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mr-2">{T('process.versions')}</h3>
              <button
                onClick={() => setActiveVersion('draft')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm ${
                  activeVersion === 'draft'
                    ? 'border-brand-300 bg-brand-50 shadow-sm text-brand-700 font-medium'
                    : 'border-gray-200 bg-white hover:border-gray-300 text-gray-600'
                }`}
              >
                <span>{T('process.draft')}</span>
                <StatusBadge status={draftStatus} T={T} />
              </button>
              <button
                onClick={() => setActiveVersion('optimized')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm ${
                  activeVersion === 'optimized'
                    ? 'border-brand-300 bg-brand-50 shadow-sm text-brand-700 font-medium'
                    : 'border-gray-200 bg-white hover:border-gray-300 text-gray-600'
                }`}
              >
                <span>{T('process.optimized')}</span>
                <StatusBadge status={optimizedStatus} T={T} />
              </button>
              <button
                onClick={() => setActiveVersion('materials')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm ${
                  activeVersion === 'materials'
                    ? 'border-teal-300 bg-teal-50 shadow-sm text-teal-700 font-medium'
                    : 'border-gray-200 bg-white hover:border-gray-300 text-gray-600'
                }`}
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>{T('process.material_tab')}</span>
                {anyMaterialGenerating && (
                  <span className="flex items-center gap-1 text-xs text-teal-600 bg-teal-50 px-1.5 py-0.5 rounded-full">
                    <Loader2 className="w-3 h-3 animate-spin" />
                  </span>
                )}
                {!anyMaterialGenerating && (materialDraftTask?.status === 'done' || materialOptimizedTask?.status === 'done') && (
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                )}
              </button>
              <div className="ml-auto">
                {activeVersion !== 'materials' && activeDocStreaming && (
                  <span className="flex items-center gap-1.5 text-xs text-brand-600 bg-brand-50 px-2.5 py-1 rounded-full animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    {T('process.streaming')}
                  </span>
                )}
                {activeVersion !== 'materials' && !activeDocStreaming && activeDocText && (
                  <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-2.5 py-1 rounded-full">
                    <CheckCircle2 className="w-3 h-3" />
                    {T('process.completed')}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Document / Materials content (independently scrollable) */}
          <div className="flex-1 panel-scroll" ref={centerPanelRef}>
            {activeVersion === 'materials' ? (
              /* ===== Materials Panel ===== */
              <div className="max-w-3xl mx-auto p-6 space-y-6">
                {/* Header */}
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-teal-600" />
                    {T('process.material_title')}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {T('process.material_desc')}
                  </p>
                </div>

                {/* Material cards for each version */}
                {([
                  { version: 'draft' as const, label: T('process.material_draft'), task: materialDraftTask, hasContent: !!fullDraftText },
                  { version: 'optimized' as const, label: T('process.material_optimized'), task: materialOptimizedTask, hasContent: !!fullOptimizedText },
                ]).map(({ version, label, task, hasContent }) => (
                  <Card key={version} className="relative overflow-hidden">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          task?.status === 'done' ? 'bg-green-100' :
                          task?.status === 'generating' ? 'bg-teal-100' :
                          task?.status === 'error' ? 'bg-red-100' : 'bg-gray-100'
                        }`}>
                          {task?.status === 'generating' ? (
                            <Loader2 className="w-5 h-5 text-teal-600 animate-spin" />
                          ) : task?.status === 'done' ? (
                            <CheckCircle2 className="w-5 h-5 text-green-600" />
                          ) : task?.status === 'error' ? (
                            <X className="w-5 h-5 text-red-500" />
                          ) : (
                            <BookOpen className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-gray-900">{label}{T('process.material_version')}</h3>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {task?.status === 'generating' && (
                              <span className="text-teal-600">
                                {T('process.material_generating')}
                              </span>
                            )}
                            {task?.status === 'done' && <span className="text-green-600">{T('process.material_done')}</span>}
                            {task?.status === 'error' && <span className="text-red-600">{task.error}</span>}
                            {!task && hasContent && <span>{T('process.material_click')}</span>}
                            {!task && !hasContent && <span className="text-gray-400">{T('process.material_no_content')}</span>}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {task?.status === 'done' && (
                          <>
                            <button
                              onClick={() => setPreviewingMaterial({
                                html: task.html,
                                title: `${currentLesson?.title || T('process.lesson_fallback')} - ${label}`,
                                version,
                              })}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              {T('process.material_preview')}
                            </button>
                            <button
                              onClick={() => {
                                const win = window.open('', '_blank')
                                if (win) { win.document.write(task.html); win.document.close() }
                              }}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-teal-700 bg-teal-50 border border-teal-200 rounded-lg hover:bg-teal-100 transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              {T('process.material_new_window')}
                            </button>
                            <button
                              onClick={() => {
                                const blob = new Blob([task.html], { type: 'text/html;charset=utf-8' })
                                const url = URL.createObjectURL(blob)
                                const a = document.createElement('a')
                                a.href = url
                                a.download = `${(currentLesson?.title || 'material').replace(/[<>:"/\\|?*]/g, '_')}_${version}_material.html`
                                document.body.appendChild(a)
                                a.click()
                                document.body.removeChild(a)
                                URL.revokeObjectURL(url)
                              }}
                              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded-lg hover:bg-gray-200 transition-colors"
                            >
                              <Download className="w-3.5 h-3.5" />
                              {T('process.material_download')}
                            </button>
                          </>
                        )}
                        {(!task || task.status === 'error') && (
                          <button
                            onClick={() => id && startMaterialGen(id, version)}
                            disabled={!hasContent || task?.status === 'generating'}
                            className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-teal-600 rounded-lg hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                          >
                            <BookOpen className="w-3.5 h-3.5" />
                            {task?.status === 'error' ? T('process.material_regenerate') : T('process.material_generate')}
                          </button>
                        )}
                        {task?.status === 'generating' && (
                          <span className="flex items-center gap-1.5 text-xs text-teal-600 bg-teal-50 px-3 py-1.5 rounded-lg">
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            {T('process.material_generating_btn')}
                          </span>
                        )}
                        {task?.status === 'done' && (
                          <button
                            onClick={() => id && startMaterialGen(id, version)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-orange-600 bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                            {T('process.material_regenerate')}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Inline preview area */}
                    {task?.status === 'generating' && (
                      <div className="mt-4 p-4 bg-teal-50/50 border border-teal-100 rounded-lg">
                        <div className="flex items-center gap-2 text-sm text-teal-700">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>{T('process.material_bg_hint')}</span>
                        </div>
                      </div>
                    )}
                  </Card>
                ))}

                {/* Tip */}
                <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
                  <BookOpen className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-700">
                    {T('process.material_time_hint')}
                  </p>
                </div>
              </div>
            ) : (
              /* ===== Document Panel (draft / optimized) ===== */
              <div className="max-w-3xl mx-auto p-6">
                {activeDocText ? (
                  <div>
                    {/* Action bar: Regenerate + Export */}
                    <div className="flex items-center justify-between mb-3">
                      <div className="relative" ref={exportMenuRef}>
                        <button
                          onClick={() => setShowExportMenu((p) => !p)}
                          disabled={!!exporting || activeDocStreaming}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                        >
                          {exporting ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Download className="w-3.5 h-3.5" />
                          )}
                          {exporting ? T('process.exporting') : T('process.export_doc')}
                          <ChevronDown className="w-3 h-3 ml-0.5" />
                        </button>
                        {showExportMenu && (
                          <div className="absolute top-full left-0 mt-1 w-48 bg-white rounded-lg border border-gray-200 shadow-lg z-50 py-1">
                            {EXPORT_FORMATS.map((f) => (
                              <button
                                key={f.key}
                                onClick={() => handleExport(f.key)}
                                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                              >
                                <span className="w-7 h-5 flex items-center justify-center text-[10px] font-bold rounded bg-gray-100 text-gray-500 shrink-0">
                                  {f.icon}
                                </span>
                                <span>{f.label}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => setShowStyledPdfModal(true)}
                        disabled={activeDocStreaming}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                      >
                        <FileType className="w-3.5 h-3.5" />
                        {T('process.styled_pdf_btn')}
                      </button>
                      <div className="flex items-center gap-2">
                        {activeVersion === 'draft' && !activeDocStreaming && (
                          <button
                            onClick={handleRegenerateDraft}
                            disabled={regeneratingDraft || fullDraftStreaming}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-orange-600 bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${regeneratingDraft ? 'animate-spin' : ''}`} />
                            {T('process.regen_draft')}
                          </button>
                        )}
                        {activeVersion === 'optimized' && !activeDocStreaming && (
                          <button
                            onClick={handleRegenerateOptimized}
                            disabled={regeneratingOptimized || fullOptimizedStreaming}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-violet-600 bg-violet-50 border border-violet-200 rounded-lg hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${regeneratingOptimized ? 'animate-spin' : ''}`} />
                            {T('process.re_optimize')}
                          </button>
                        )}
                      </div>
                    </div>
                    <Card className="relative">
                      <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                        {activeDocText}
                        {activeDocStreaming && (
                          <span className="inline-block w-0.5 h-4 bg-brand-500 ml-0.5 animate-pulse" />
                        )}
                      </div>
                    </Card>
                  </div>
                ) : (
                  <Card>
                    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                      {activeVersion === 'draft' && !fullDraftText ? (
                        <>
                          <Loader2 className="w-8 h-8 animate-spin mb-3 text-brand-400" />
                          <span className="text-sm">{T('process.waiting')}</span>
                        </>
                      ) : activeVersion === 'optimized' && !fullOptimizedText ? (
                        <>
                          <Clock className="w-8 h-8 mb-3" />
                          <span className="text-sm">{T('process.waiting')}</span>
                        </>
                      ) : null}
                    </div>
                  </Card>
                )}
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Styled PDF Modal */}
      {showStyledPdfModal && (
        <StyledPdfModal
          lessonId={id!}
          lessonTitle={currentLesson?.title || T('process.lesson_fallback')}
          hasDraft={!!fullDraftText}
          hasOptimized={!!fullOptimizedText}
          isGenerating={styledPdfTask?.status === 'generating'}
          onClose={() => setShowStyledPdfModal(false)}
        />
      )}

      {/* Material preview modal */}
      {previewingMaterial && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setPreviewingMaterial(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-[900px] max-h-[90vh] flex flex-col overflow-hidden">
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-teal-100 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-teal-600" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-gray-900">{T('process.material_preview_title')}</h2>
                  <p className="text-xs text-gray-500">{previewingMaterial.title}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const win = window.open('', '_blank')
                    if (win) { win.document.write(previewingMaterial.html); win.document.close() }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  {T('process.material_preview_new')}
                </button>
                <button
                  onClick={() => {
                    const blob = new Blob([previewingMaterial.html], { type: 'text/html;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `${previewingMaterial.title.replace(/[<>:"/\\|?*]/g, '_')}.html`
                    document.body.appendChild(a)
                    a.click()
                    document.body.removeChild(a)
                    URL.revokeObjectURL(url)
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  {T('process.material_download_html')}
                </button>
                <button onClick={() => setPreviewingMaterial(null)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors ml-1">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              <iframe
                srcDoc={previewingMaterial.html}
                title="Course Material Preview"
                className="w-full h-full border-0"
                style={{ minHeight: '600px' }}
                sandbox="allow-same-origin allow-scripts"
              />
            </div>
          </div>
        </div>
      )}

      {/* Styled PDF floating indicator */}
      {styledPdfTask && !showStyledPdfModal && (
        <div className="fixed bottom-6 right-6 z-50">
          {styledPdfTask.status === 'generating' && (
            <div className="flex items-center gap-3 bg-white border border-indigo-200 shadow-lg rounded-xl px-4 py-3 animate-in slide-in-from-bottom-2">
              <Loader2 className="w-4 h-4 text-indigo-600 animate-spin flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900">{T('process.styled_generating')}</p>
                <p className="text-xs text-gray-500">{T('process.styled_bg')}</p>
              </div>
            </div>
          )}

          {styledPdfTask.status === 'done' && !showStyledPdfResult && !styledPdfDismissed && (
            <div className="flex items-center gap-3 bg-white border border-green-200 shadow-lg rounded-xl px-4 py-3 cursor-pointer hover:shadow-xl transition-shadow"
              onClick={() => setShowStyledPdfResult(true)}
            >
              <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-900">{T('process.styled_done')}</p>
                <p className="text-xs text-indigo-600 font-medium">{T('process.styled_click')}</p>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); setStyledPdfDismissed(true) }}
                className="ml-2 p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {styledPdfTask.status === 'error' && (
            <div className="flex items-center gap-3 bg-white border border-red-200 shadow-lg rounded-xl px-4 py-3">
              <div className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                <X className="w-3 h-3 text-red-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{T('process.styled_failed')}</p>
                <p className="text-xs text-red-600">{styledPdfTask.error}</p>
              </div>
              <button
                onClick={() => setShowStyledPdfResult(false)}
                className="ml-2 p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Material generation floating indicator (only when NOT on materials tab) */}
      {anyMaterialGenerating && activeVersion !== 'materials' && (
        <div className="fixed bottom-6 right-6 z-50" style={{ marginBottom: styledPdfTask && !showStyledPdfModal ? '60px' : '0' }}>
          <div
            className="flex items-center gap-3 bg-white border border-teal-200 shadow-lg rounded-xl px-4 py-3 cursor-pointer hover:shadow-xl transition-shadow animate-in slide-in-from-bottom-2"
            onClick={() => setActiveVersion('materials')}
          >
            <Loader2 className="w-4 h-4 text-teal-600 animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-gray-900">{T('process.material_float')}</p>
              <p className="text-xs text-gray-500">{T('process.material_float_click')}</p>
            </div>
          </div>
        </div>
      )}

      {/* Styled PDF result viewer */}
      {showStyledPdfResult && styledPdfTask?.status === 'done' && styledPdfTask.html && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowStyledPdfResult(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-[900px] max-h-[90vh] flex flex-col overflow-hidden">
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-green-100 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-gray-900">{T('process.styled_title_done')}</h2>
                  <p className="text-xs text-gray-500">{currentLesson?.title || T('process.lesson_fallback')} · {styledPdfTask.contentVersion === 'draft' ? T('process.material_draft') : T('process.material_optimized')}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const win = window.open('', '_blank')
                    if (win) { win.document.write(styledPdfTask.html); win.document.close() }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  {T('process.styled_preview')}
                </button>
                <button
                  onClick={() => {
                    const win = window.open('', '_blank')
                    if (win) {
                      win.document.write(styledPdfTask.html)
                      win.document.close()
                      win.onload = () => setTimeout(() => win.print(), 500)
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg hover:bg-indigo-100 transition-colors"
                >
                  <Printer className="w-3.5 h-3.5" />
                  {T('process.styled_print')}
                </button>
                <button
                  onClick={() => {
                    const blob = new Blob([styledPdfTask.html], { type: 'text/html;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `${(currentLesson?.title || 'lesson').replace(/[<>:"/\\|?*]/g, '_')}_styled.html`
                    document.body.appendChild(a)
                    a.click()
                    document.body.removeChild(a)
                    URL.revokeObjectURL(url)
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  {T('process.styled_download_html')}
                </button>
                <button onClick={() => setShowStyledPdfResult(false)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors ml-1">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden">
              <iframe
                srcDoc={styledPdfTask.html}
                title="Styled PDF Preview"
                className="w-full h-full border-0"
                style={{ minHeight: '600px' }}
                sandbox="allow-same-origin"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const MODEL_BADGE_COLORS = [
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-violet-100 text-violet-700',
  'bg-amber-100 text-amber-700',
  'bg-rose-100 text-rose-700',
  'bg-cyan-100 text-cyan-700',
  'bg-fuchsia-100 text-fuchsia-700',
  'bg-lime-100 text-lime-700',
]

function ModelRecommendationCard({
  streamingText,
  isStreaming,
  models,
  overallReason,
  T,
}: {
  streamingText: string
  isStreaming: boolean
  models: ActiveModel[]
  overallReason?: string
  T: (key: string) => string
}) {
  const hasFinished = !isStreaming && models.length > 0
  const model = hasFinished ? models[0] : null
  const [showReason, setShowReason] = useState(false)
  const reasonText = overallReason || model?.reason || ''

  return (
    <div className="mb-4">
      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">{T('process.model_title')}</h3>
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {isStreaming && (
          <div className="p-3 text-xs text-gray-600 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
            {streamingText}
            <span className="inline-block w-0.5 h-3 bg-brand-500 ml-0.5 animate-pulse" />
          </div>
        )}

        {hasFinished && model && (
          <div className="p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className={`text-xs font-semibold px-2 py-1 rounded ${MODEL_BADGE_COLORS[0]}`}>
                {model.name}
              </span>
              {reasonText && (
                <button
                  onClick={() => setShowReason(true)}
                  className="flex items-center gap-1 text-[11px] text-brand-600 hover:text-brand-700 font-medium transition-colors"
                >
                  <Eye className="w-3 h-3" />
                  {T('process.view_reason')}
                </button>
              )}
            </div>

            <div>
              <p className="text-[10px] text-gray-400 mb-1">{T('process.teaching_stages')}</p>
              <div className="flex flex-wrap gap-1">
                {model.stages.map((stage, j) => (
                  <span key={stage} className="text-[9px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
                    {j + 1}. {stage}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {showReason && model && reasonText && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-[6px]" onClick={() => setShowReason(false)} />
            <div className="relative w-[460px] max-w-full max-h-[85vh] flex flex-col rounded-2xl overflow-hidden shadow-[0_25px_60px_-12px_rgba(0,0,0,0.3)]">
              {/* 顶部渐变头 */}
              <div className="relative bg-gradient-to-br from-violet-600 via-brand-600 to-indigo-600 px-6 py-5">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.15),transparent_70%)]" />
                <button
                  onClick={() => setShowReason(false)}
                  className="absolute top-3 right-3 p-1.5 rounded-full bg-white/15 hover:bg-white/25 text-white/80 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="relative flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
                    <BookOpen className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold text-[15px]">{T('process.model_analysis')}</h3>
                    <p className="text-white/60 text-[11px]">{T('process.model_analysis_desc')}</p>
                  </div>
                </div>
                <div className="relative inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm rounded-lg px-3 py-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-300 animate-pulse" />
                  <span className="text-white font-semibold text-xs">{model.name}</span>
                </div>
              </div>

              {/* 内容区 */}
              <div className="flex-1 bg-white overflow-y-auto">
                {/* 选用原因 */}
                <div className="px-6 py-5 border-b border-gray-100">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="w-1 h-4 rounded-full bg-brand-500" />
                    <p className="text-xs font-semibold text-gray-800 tracking-wide">{T('process.reason_title')}</p>
                  </div>
                  <p className="text-[13px] text-gray-600 leading-[1.8] pl-3">{reasonText}</p>
                </div>

                {/* 模型特点 */}
                {model.reason && overallReason && model.reason !== overallReason && (
                  <div className="px-6 py-5 border-b border-gray-100">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="w-1 h-4 rounded-full bg-violet-500" />
                      <p className="text-xs font-semibold text-gray-800 tracking-wide">{T('process.model_features')}</p>
                    </div>
                    <p className="text-[13px] text-gray-600 leading-[1.8] pl-3">{model.reason}</p>
                  </div>
                )}

                {/* 教学阶段 */}
                <div className="px-6 py-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="w-1 h-4 rounded-full bg-indigo-500" />
                      <p className="text-xs font-semibold text-gray-800 tracking-wide">{T('process.teaching_stages')}</p>
                    </div>
                    <span className="text-[10px] font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{T('process.stage_count').replace('{n}', String(model.stages.length))}</span>
                  </div>
                  <div className="relative pl-3">
                    <div className="absolute left-[12px] top-2 bottom-2 w-px bg-gradient-to-b from-brand-200 via-violet-200 to-indigo-200" />
                    <div className="space-y-3">
                      {model.stages.map((stage, j) => (
                        <div key={stage} className="flex items-center gap-3 group">
                          <span className="relative z-10 w-6 h-6 rounded-full bg-gradient-to-br from-brand-500 to-violet-500 text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0 shadow-sm group-hover:scale-110 transition-transform">
                            {j + 1}
                          </span>
                          <span className="text-[13px] text-gray-700 group-hover:text-gray-900 transition-colors">{stage}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* 底部 */}
              <div className="bg-gray-50 border-t border-gray-100 px-6 py-3 flex justify-end">
                <button
                  onClick={() => setShowReason(false)}
                  className="px-5 py-2 text-xs font-medium text-white bg-gradient-to-r from-brand-600 to-violet-600 rounded-lg hover:shadow-md hover:shadow-brand-200/50 transition-all"
                >
                  {T('process.got_it')}
                </button>
              </div>
            </div>
          </div>
        )}

        {!isStreaming && !hasFinished && streamingText && (
          <div className="p-3 text-xs text-gray-500 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
            {streamingText}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status, T }: { status: string; T: (key: string) => string }) {
  if (status === 'streaming') {
    return (
      <span className="flex items-center gap-1 text-xs text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
        <Loader2 className="w-3 h-3 animate-spin" />
        {T('process.streaming')}
      </span>
    )
  }
  if (status === 'done') {
    return (
      <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
        <CheckCircle2 className="w-3 h-3" />
        {T('process.completed')}
      </span>
    )
  }
  return (
    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
      {T('process.waiting')}
    </span>
  )
}
