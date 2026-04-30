import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { toast } from '../components/ui/Toast'
import { useDocumentsStore, DocumentVersionFull, DocumentVersionBrief } from '../stores/documentsStore'
import { useAuthStore } from '../stores/authStore'
import {
  Save,
  History,
  Wand2,
  Loader2,
  ChevronLeft,
  Download,
  RotateCcw,
  Sparkles,
  CornerUpLeft,
  X,
} from 'lucide-react'

type AiMode = 'document' | 'paragraph' | null

export default function DocumentEditor() {
  const { versionId } = useParams<{ versionId: string }>()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || ''
  const docScope = forUserId ? { for_user_id: forUserId } : undefined
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  const t = useT()
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.token)
  const {
    current, fetchVersion, createVersion,
    versions, fetchVersionsForLesson, setCurrentVersion, deleteVersion,
  } = useDocumentsStore()

  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [savingNote, setSavingNote] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const [saving, setSaving] = useState(false)

  const [aiMode, setAiMode] = useState<AiMode>(null)
  const [aiInstruction, setAiInstruction] = useState('')
  const [aiResult, setAiResult] = useState('')
  const [aiBusy, setAiBusy] = useState(false)
  const aiAbortRef = useRef<AbortController | null>(null)
  const [paragraph, setParagraph] = useState('')
  const [paragraphCtx, setParagraphCtx] = useState<{ before: string; after: string }>({ before: '', after: '' })

  useEffect(() => {
    if (!versionId) return
    fetchVersion(versionId).then((v) => {
      setText(v.content_markdown || '')
      setTitle(v.title || '')
      if (v.lesson_plan_id) {
        fetchVersionsForLesson(v.lesson_plan_id, v.source_kind, docScope)
      }
    }).catch((e) => {
      toast.error(e?.response?.data?.detail || t('doc.load_failed'))
    })
  }, [versionId, fetchVersion, fetchVersionsForLesson, t, forUserId])

  const dirty = current ? text !== (current.content_markdown || '') || title !== (current.title || '') : false

  const handleSave = async () => {
    if (!current) return
    if (!text.trim()) {
      toast.error(t('doc.error_empty'))
      return
    }
    setSaving(true)
    try {
      const created = await createVersion({
        lesson_plan_id: current.lesson_plan_id,
        source_kind: current.source_kind,
        source_ref_id: current.source_ref_id,
        title: title.trim() || current.title,
        content_markdown: text,
        parent_version_id: current.id,
        change_source: 'user_edit',
        change_summary: savingNote || t('doc.change_user_edit'),
      }, docScope)
      toast.success(t('doc.save_success'))
      setSavingNote('')
      if (current.lesson_plan_id) {
        fetchVersionsForLesson(current.lesson_plan_id, current.source_kind, docScope)
      }
      navigate(`/documents/version/${created.id}${scopeQs}`, { replace: true })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('doc.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  const handleSwitchVersion = async (vid: string) => {
    if (dirty && !window.confirm(t('doc.confirm_discard'))) return
    navigate(`/documents/version/${vid}${scopeQs}`)
  }

  const handleSetCurrent = async (vid: string) => {
    try {
      await setCurrentVersion(vid)
      if (current?.lesson_plan_id) {
        fetchVersionsForLesson(current.lesson_plan_id, current.source_kind, docScope)
      }
      toast.success(t('doc.set_current_success'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('doc.set_current_failed'))
    }
  }

  const handleDeleteVersion = async (vid: string) => {
    if (!window.confirm(t('doc.confirm_delete_version'))) return
    try {
      await deleteVersion(vid)
      toast.success(t('doc.delete_success'))
      if (vid === versionId) {
        const remaining = versions.filter((v) => v.id !== vid)
        if (remaining.length) {
          navigate(`/documents/version/${remaining[0].id}${scopeQs}`, { replace: true })
        } else {
          navigate(`/documents${scopeQs}`, { replace: true })
        }
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('doc.delete_failed'))
    }
  }

  const startAiDocument = () => {
    setAiMode('document')
    setAiInstruction('')
    setAiResult('')
  }

  const startAiParagraph = () => {
    const ta = document.getElementById('doc-editor-textarea') as HTMLTextAreaElement | null
    if (!ta) return
    const start = ta.selectionStart || 0
    const end = ta.selectionEnd || 0
    if (end <= start) {
      toast.info(t('doc.select_paragraph_first'))
      return
    }
    const para = text.slice(start, end)
    if (!para.trim()) {
      toast.info(t('doc.select_paragraph_first'))
      return
    }
    setParagraph(para)
    setParagraphCtx({
      before: text.slice(Math.max(0, start - 800), start),
      after: text.slice(end, end + 800),
    })
    setAiMode('paragraph')
    setAiInstruction('')
    setAiResult('')
  }

  const callAi = async () => {
    if (!aiInstruction.trim()) {
      toast.error(t('doc.ai_instruction_required'))
      return
    }
    setAiBusy(true)
    setAiResult('')
    aiAbortRef.current?.abort()
    const ctl = new AbortController()
    aiAbortRef.current = ctl

    try {
      const url = aiMode === 'document'
        ? '/api/v1/documents/revise/document'
        : '/api/v1/documents/revise/paragraph'
      const body = aiMode === 'document'
        ? { instruction: aiInstruction, full_markdown: text }
        : {
            instruction: aiInstruction,
            paragraph,
            context_before: paragraphCtx.before,
            context_after: paragraphCtx.after,
          }
      const res = await fetch(url, {
        method: 'POST',
        signal: ctl.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      })
      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => '')
        throw new Error(detail || `${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          let event = 'message'
          let data = ''
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) data += line.slice(5).trim()
          }
          if (!data) continue
          try {
            const obj = JSON.parse(data)
            if (event === 'chunk' && obj.text) {
              setAiResult((prev) => prev + obj.text)
            } else if (event === 'error') {
              throw new Error(obj.message || 'AI error')
            }
          } catch (parseErr) {
            // ignore parse errors
          }
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') {
        toast.error(e?.message || t('doc.ai_failed'))
      }
    } finally {
      setAiBusy(false)
    }
  }

  const cancelAi = () => {
    aiAbortRef.current?.abort()
    setAiBusy(false)
  }

  const applyAi = () => {
    if (!aiResult) return
    if (aiMode === 'document') {
      setText(aiResult)
      setSavingNote(t('doc.change_ai_full') + (aiInstruction ? `: ${aiInstruction.slice(0, 80)}` : ''))
    } else if (aiMode === 'paragraph') {
      const newText = text.replace(paragraph, aiResult)
      setText(newText)
      setSavingNote(t('doc.change_ai_paragraph') + (aiInstruction ? `: ${aiInstruction.slice(0, 80)}` : ''))
    }
    setAiMode(null)
    setAiResult('')
    setAiInstruction('')
    toast.success(t('doc.ai_applied_hint'))
  }

  const handleDownload = (format: 'markdown' | 'pdf' | 'docx') => {
    if (!current) return
    if (!current.lesson_plan_id) {
      toast.info(t('doc.download_requires_lesson'))
      return
    }
    const q = new URLSearchParams()
    q.set('version_id', current.id)
    if (forUserId) q.set('for_user_id', forUserId)
    const url = `/api/v1/export/${format}/${current.lesson_plan_id}?${q.toString()}`
    const a = document.createElement('a')
    a.href = url
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const previewHtml = useMemo(() => mdToSafeHtml(text), [text])

  if (!current) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <main className="max-w-7xl mx-auto px-6 py-20 text-center">
          <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" />
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2 min-w-0">
            <Link to="/documents" className="text-gray-500 hover:text-brand-600">
              <ChevronLeft className="w-5 h-5" />
            </Link>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="text-xl font-bold text-gray-900 bg-transparent border-b border-transparent hover:border-gray-300 focus:border-brand-500 focus:outline-none px-1 truncate"
              placeholder={t('doc.title_placeholder')}
            />
            <span className="text-xs text-gray-400 shrink-0">
              v{current.version_number}
              {current.is_current && (
                <span className="ml-1 text-green-600">· {t('doc.is_current')}</span>
              )}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="ghost" size="sm" onClick={() => setShowHistory((v) => !v)}>
              <History className="w-4 h-4 mr-1" />
              {t('doc.history')} ({versions.length})
            </Button>
            <Button variant="ghost" size="sm" onClick={() => handleDownload('markdown')}>
              <Download className="w-4 h-4 mr-1" />
              MD
            </Button>
            <Button variant="ghost" size="sm" onClick={() => handleDownload('docx')}>
              <Download className="w-4 h-4 mr-1" />
              DOCX
            </Button>
            <Button variant="ghost" size="sm" onClick={() => handleDownload('pdf')}>
              <Download className="w-4 h-4 mr-1" />
              PDF
            </Button>
            <Button onClick={handleSave} disabled={saving || !dirty} size="sm">
              {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
              {t('doc.save_new_version')}
            </Button>
          </div>
        </div>

        {dirty && (
          <input
            value={savingNote}
            onChange={(e) => setSavingNote(e.target.value)}
            placeholder={t('doc.change_summary_placeholder')}
            className="w-full mb-3 text-sm px-3 py-1.5 border border-amber-200 bg-amber-50 rounded-lg focus:outline-none focus:border-amber-400"
          />
        )}

        <div className={`grid gap-4 ${showHistory ? 'lg:grid-cols-[260px_minmax(0,1fr)_360px]' : 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]'}`}>
          {showHistory && (
            <Card padding={false}>
              <div className="p-3 border-b font-medium text-sm text-gray-700 flex items-center justify-between">
                <span className="flex items-center gap-1.5"><History className="w-4 h-4" />{t('doc.history')}</span>
                <button onClick={() => setShowHistory(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="max-h-[calc(100vh-260px)] overflow-y-auto divide-y">
                {versions.map((v) => (
                  <VersionRow
                    key={v.id}
                    v={v}
                    active={v.id === versionId}
                    onOpen={() => handleSwitchVersion(v.id)}
                    onSetCurrent={() => handleSetCurrent(v.id)}
                    onDelete={() => handleDeleteVersion(v.id)}
                    t={t}
                  />
                ))}
              </div>
            </Card>
          )}

          <Card padding={false}>
            <div className="p-2 border-b flex items-center justify-between">
              <span className="text-sm text-gray-600 px-2">{t('doc.editor_pane')}</span>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="ghost" onClick={startAiDocument}>
                  <Sparkles className="w-4 h-4 mr-1" />
                  {t('doc.ai_full_doc')}
                </Button>
                <Button size="sm" variant="ghost" onClick={startAiParagraph}>
                  <Wand2 className="w-4 h-4 mr-1" />
                  {t('doc.ai_paragraph')}
                </Button>
              </div>
            </div>
            <textarea
              id="doc-editor-textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              className="w-full h-[calc(100vh-260px)] p-4 font-mono text-sm leading-relaxed resize-none focus:outline-none"
              placeholder={t('doc.editor_placeholder')}
            />
          </Card>

          <Card padding={false} className={showHistory ? 'hidden xl:block' : ''}>
            <div className="p-2 border-b text-sm text-gray-600 px-3 flex items-center gap-2">
              <span>{t('doc.preview_pane')}</span>
              <span className="text-[11px] text-gray-400">{t('doc.preview_hint')}</span>
            </div>
            <div
              className="prose max-w-none h-[calc(100vh-260px)] overflow-y-auto p-6"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
            />
          </Card>
        </div>

        {aiMode && (
          <AiPanel
            mode={aiMode}
            instruction={aiInstruction}
            setInstruction={setAiInstruction}
            paragraph={aiMode === 'paragraph' ? paragraph : ''}
            result={aiResult}
            busy={aiBusy}
            onClose={() => { cancelAi(); setAiMode(null); setAiResult('') }}
            onSubmit={callAi}
            onCancel={cancelAi}
            onApply={applyAi}
            t={t}
          />
        )}
      </main>
    </div>
  )
}

function VersionRow({
  v, active, onOpen, onSetCurrent, onDelete, t,
}: {
  v: DocumentVersionBrief
  active: boolean
  onOpen: () => void
  onSetCurrent: () => void
  onDelete: () => void
  t: (k: string) => string
}) {
  const sourceLabel: Record<string, string> = {
    user_edit: t('doc.change_user_edit'),
    ai_full: t('doc.change_ai_full'),
    ai_paragraph: t('doc.change_ai_paragraph'),
    system_init: t('doc.change_system_init'),
  }
  return (
    <div className={`p-3 hover:bg-gray-50 transition-colors ${active ? 'bg-brand-50' : ''}`}>
      <div className="flex items-center justify-between">
        <button onClick={onOpen} className="text-left flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700">
            <span>v{v.version_number}</span>
            {v.is_current && <span className="text-green-600 text-[10px] px-1 bg-green-50 rounded">{t('doc.is_current')}</span>}
          </div>
          <div className="text-xs text-gray-500 truncate mt-0.5">
            {sourceLabel[v.change_source] || v.change_source}
            {v.change_summary ? `: ${v.change_summary}` : ''}
          </div>
          <div className="text-[10px] text-gray-400 mt-0.5">
            {v.created_at ? new Date(v.created_at).toLocaleString() : ''}
          </div>
        </button>
        <div className="flex items-center gap-1 ml-2 shrink-0">
          {!v.is_current && (
            <button
              onClick={onSetCurrent}
              title={t('doc.set_as_current')}
              className="p-1 text-gray-400 hover:text-brand-600"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={onDelete}
            title={t('doc.delete')}
            className="p-1 text-gray-400 hover:text-red-500"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}

function AiPanel({
  mode, instruction, setInstruction, paragraph, result, busy,
  onClose, onSubmit, onCancel, onApply, t,
}: {
  mode: 'document' | 'paragraph'
  instruction: string
  setInstruction: (s: string) => void
  paragraph: string
  result: string
  busy: boolean
  onClose: () => void
  onSubmit: () => void
  onCancel: () => void
  onApply: () => void
  t: (k: string) => string
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-3" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[88vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center gap-2 font-semibold">
            {mode === 'document' ? <Sparkles className="w-5 h-5 text-purple-500" /> : <Wand2 className="w-5 h-5 text-blue-500" />}
            {mode === 'document' ? t('doc.ai_full_doc') : t('doc.ai_paragraph')}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 space-y-3 overflow-y-auto">
          {mode === 'paragraph' && (
            <div>
              <div className="text-xs font-medium text-gray-600 mb-1">{t('doc.selected_paragraph')}</div>
              <div className="text-sm bg-gray-50 border rounded-lg p-3 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {paragraph}
              </div>
            </div>
          )}
          <div>
            <div className="text-xs font-medium text-gray-600 mb-1">{t('doc.ai_instruction_label')}</div>
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder={t('doc.ai_instruction_placeholder')}
              className="w-full text-sm border rounded-lg p-3 focus:outline-none focus:border-brand-500 min-h-[80px]"
            />
          </div>
          {result && (
            <div>
              <div className="text-xs font-medium text-gray-600 mb-1">{t('doc.ai_result')}</div>
              <div className="text-sm bg-purple-50 border border-purple-200 rounded-lg p-3 max-h-64 overflow-y-auto whitespace-pre-wrap">
                {result}
                {busy && <Loader2 className="w-4 h-4 inline-block ml-2 animate-spin text-purple-500" />}
              </div>
            </div>
          )}
        </div>
        <div className="p-4 border-t flex items-center justify-end gap-2">
          {busy ? (
            <Button variant="ghost" onClick={onCancel}>
              <X className="w-4 h-4 mr-1" />
              {t('doc.ai_cancel')}
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose}>
                <CornerUpLeft className="w-4 h-4 mr-1" />
                {t('doc.ai_close')}
              </Button>
              {result && (
                <Button onClick={onApply} variant="secondary">
                  {t('doc.ai_apply')}
                </Button>
              )}
              <Button onClick={onSubmit} disabled={!instruction.trim()}>
                <Sparkles className="w-4 h-4 mr-1" />
                {result ? t('doc.ai_resubmit') : t('doc.ai_submit')}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// 极简 markdown→HTML（仅 # 标题 / 粗体 / 斜体 / 行内代码 / 段落 / 列表），并 escape
// 用于编辑器右侧实时预览。生成器/导出仍走后端 reportlab，前端只是给作者看大致效果。
function mdToSafeHtml(md: string): string {
  if (!md) return '<p class="text-gray-400">…</p>'
  const escape = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const lines = md.split('\n')
  const out: string[] = []
  let inUl = false, inOl = false, inCode = false
  const flushList = () => {
    if (inUl) { out.push('</ul>'); inUl = false }
    if (inOl) { out.push('</ol>'); inOl = false }
  }
  const inline = (s: string) =>
    escape(s)
      .replace(/`([^`]+)`/g, '<code class="px-1 bg-gray-100 rounded text-[0.85em]">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')

  for (const raw of lines) {
    const line = raw
    if (/^```/.test(line)) {
      flushList()
      if (!inCode) { out.push('<pre class="bg-gray-900 text-gray-100 rounded p-3 text-xs overflow-x-auto"><code>'); inCode = true }
      else { out.push('</code></pre>'); inCode = false }
      continue
    }
    if (inCode) { out.push(escape(line) + '\n'); continue }
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      flushList()
      const lvl = h[1].length
      out.push(`<h${lvl} class="font-semibold mt-4 mb-2">${inline(h[2])}</h${lvl}>`)
      continue
    }
    const ul = line.match(/^[-*]\s+(.*)$/)
    if (ul) {
      if (!inUl) { flushList(); out.push('<ul class="list-disc pl-6 my-2 space-y-0.5">'); inUl = true }
      out.push(`<li>${inline(ul[1])}</li>`)
      continue
    }
    const ol = line.match(/^\d+\.\s+(.*)$/)
    if (ol) {
      if (!inOl) { flushList(); out.push('<ol class="list-decimal pl-6 my-2 space-y-0.5">'); inOl = true }
      out.push(`<li>${inline(ol[1])}</li>`)
      continue
    }
    if (!line.trim()) { flushList(); continue }
    flushList()
    out.push(`<p class="my-2 leading-relaxed">${inline(line)}</p>`)
  }
  flushList()
  if (inCode) out.push('</code></pre>')
  return out.join('')
}
