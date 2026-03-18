import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLessonStore } from '../stores/lessonStore'
import { getSocket, joinLesson, leaveLesson } from '../services/socket'
import { useAuthStore } from '../stores/authStore'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { ArrowLeft, Zap, Loader2, CheckCircle2, Download, FileText, Eye } from 'lucide-react'

const EXPORT_FORMATS = [
  { key: 'json', label: 'JSON', icon: '{ }' },
  { key: 'txt', label: 'TXT', icon: 'Aa' },
  { key: 'markdown', label: 'Markdown', icon: 'Md' },
  { key: 'docx', label: 'Word', icon: 'W' },
  { key: 'pdf', label: 'PDF', icon: 'Pdf' },
]

export default function QuickGenerate() {
  const navigate = useNavigate()
  const { createLesson, fetchLesson, currentLesson } = useLessonStore()

  const [topic, setTopic] = useState('')
  const [subject, setSubject] = useState('')
  const [gradeLevel, setGradeLevel] = useState('middle')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const [lessonId, setLessonId] = useState<string | null>(null)
  const [draftText, setDraftText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)

  const contentRef = useRef<HTMLDivElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!topic.trim()) {
      setError('请输入教案主题')
      return
    }
    setCreating(true)
    setError('')
    try {
      const form = new FormData()
      form.append('title', topic)
      form.append('subject', subject || '综合')
      form.append('grade_level', gradeLevel)
      form.append('source_type', 'manual')
      form.append('source_content', topic)
      form.append('mode', 'quick')
      const id = await createLesson(form)
      setLessonId(id)
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建失败，请重试')
      setCreating(false)
    }
  }

  useEffect(() => {
    if (!lessonId) return
    fetchLesson(lessonId)
  }, [lessonId, fetchLesson])

  useEffect(() => {
    if (!lessonId) return
    const socket = getSocket()
    joinLesson(lessonId)

    socket.on('stream_start', (data: any) => {
      if (data.lesson_id !== lessonId) return
      if (data.phase === 'full_draft') {
        setStreaming(true)
        setDraftText('')
        setCreating(false)
      }
    })

    socket.on('stream_chunk', (data: any) => {
      if (data.lesson_id !== lessonId) return
      if (data.phase === 'full_draft') {
        setDraftText((prev) => prev + data.chunk)
      }
    })

    socket.on('stream_end', (data: any) => {
      if (data.lesson_id !== lessonId) return
      if (data.phase === 'full_draft') {
        setDraftText(data.full_text || '')
        setStreaming(false)
      }
    })

    socket.on('lesson_completed', (data: any) => {
      if (data.lesson_id !== lessonId) return
      setIsComplete(true)
      setStreaming(false)
      setCreating(false)
      fetchLesson(lessonId)
    })

    socket.on('progress_update', (data: any) => {
      if (data.lesson_id !== lessonId) return
      if (data.status === 'failed') {
        setError(data.error || '生成失败')
        setStreaming(false)
        setCreating(false)
      }
    })

    return () => {
      leaveLesson(lessonId)
      socket.off('stream_start')
      socket.off('stream_chunk')
      socket.off('stream_end')
      socket.off('lesson_completed')
      socket.off('progress_update')
    }
  }, [lessonId, fetchLesson])

  useEffect(() => {
    if (!currentLesson || currentLesson.id !== lessonId) return
    const fc = currentLesson.final_content
    if (fc?.full_draft && !streaming && !draftText) {
      setDraftText(fc.full_draft)
    }
    if (currentLesson.status === 'completed') {
      setIsComplete(true)
      setCreating(false)
    }
  }, [currentLesson, lessonId, streaming, draftText])

  useEffect(() => {
    if (contentRef.current && streaming) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [draftText, streaming])

  const handleExport = async (format: string) => {
    if (!lessonId) return
    setExporting(format)
    try {
      const token = useAuthStore.getState().token
      const res = await fetch(`/api/v1/export/${format}/${lessonId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || '导出失败')
      }
      const blob = await res.blob()
      const ext = format === 'markdown' ? 'md' : format
      const safeName = (topic || 'lesson_plan').replace(/[<>:"/\\|?*]/g, '_')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${safeName}.${ext}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: any) {
      alert(e.message || '导出失败')
    } finally {
      setExporting(null)
    }
  }

  const selectClasses = 'w-full px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500'
  const hasStarted = !!lessonId

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <button onClick={() => navigate('/dashboard')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6">
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>

        {!hasStarted ? (
          /* ===== Input Form ===== */
          <div className="max-w-xl mx-auto">
            <div className="text-center mb-8">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Zap className="w-7 h-7 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">快速生成教案</h1>
              <p className="text-sm text-gray-500 mt-2">输入主题，AI 直接生成初步教案，无需等待多轮讨论</p>
            </div>

            {error && (
              <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
            )}

            <form onSubmit={handleSubmit}>
              <Card className="space-y-4">
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700">教案主题 *</label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="例：光合作用的原理与过程"
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400"
                    autoFocus
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">学科</label>
                    <input
                      type="text"
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                      placeholder="例：生物"
                      className={selectClasses}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">学段</label>
                    <select value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)} className={selectClasses}>
                      <option value="primary">小学</option>
                      <option value="middle">初中</option>
                      <option value="high">高中</option>
                      <option value="college">大学</option>
                    </select>
                  </div>
                </div>
              </Card>

              <div className="flex justify-center mt-6">
                <Button type="submit" disabled={creating} size="lg" className="px-12">
                  {creating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      正在创建...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4 mr-2" />
                      快速生成
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        ) : (
          /* ===== Streaming Preview + Downloads ===== */
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isComplete ? 'bg-green-100' : 'bg-amber-100'}`}>
                  {isComplete ? (
                    <CheckCircle2 className="w-5 h-5 text-green-600" />
                  ) : (
                    <Loader2 className="w-5 h-5 text-amber-600 animate-spin" />
                  )}
                </div>
                <div>
                  <h1 className="text-lg font-bold text-gray-900">{topic}</h1>
                  <p className="text-xs text-gray-500">
                    {isComplete ? '教案生成完成' : streaming ? '正在生成中...' : creating ? '正在初始化...' : '准备中...'}
                  </p>
                </div>
              </div>

              {isComplete && (
                <div className="flex items-center gap-2">
                  {EXPORT_FORMATS.map((f) => (
                    <button
                      key={f.key}
                      onClick={() => handleExport(f.key)}
                      disabled={!!exporting}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                    >
                      {exporting === f.key ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <span className="w-5 text-[10px] font-bold text-gray-400">{f.icon}</span>
                      )}
                      {f.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
            )}

            <Card className="relative">
              <div
                ref={contentRef}
                className="max-h-[calc(100vh-280px)] overflow-y-auto"
              >
                {draftText ? (
                  <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {draftText}
                    {streaming && (
                      <span className="inline-block w-0.5 h-4 bg-brand-500 ml-0.5 animate-pulse" />
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-gray-400">
                    <Loader2 className="w-8 h-8 animate-spin mb-3 text-amber-400" />
                    <span className="text-sm">AI 正在生成教案，请稍候...</span>
                  </div>
                )}
              </div>
            </Card>

            {isComplete && (
              <div className="flex justify-center gap-3 mt-6">
                <Button variant="secondary" onClick={() => { setLessonId(null); setDraftText(''); setIsComplete(false); setTopic(''); setCreating(false) }}>
                  <Zap className="w-4 h-4 mr-1.5" />
                  再生成一份
                </Button>
                <Button onClick={() => navigate(`/lesson/${lessonId}/process`)}>
                  <Eye className="w-4 h-4 mr-1.5" />
                  查看完整流程
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
