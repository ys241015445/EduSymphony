import { useState, useEffect, useRef } from 'react'
import { api } from '../../services/api'
import { useAuthStore } from '../../stores/authStore'
import Button from '../ui/Button'
import { useT } from '../../i18n/translations'
import { SourceRef, applySourceToFormData } from './SourcePicker'
import { useJobsStore } from '../../stores/jobsStore'
import { toast } from '../ui/Toast'
import { getSocket } from '../../services/socket'
import {
  Loader2, Sparkles, Palette, RefreshCw, Download, Check, Eye, Code2,
} from 'lucide-react'

export interface PaletteShape {
  bg: string; title_color: string; body_color: string
  accent: string; section_bg: string; bullet_color: string
}

export interface StyleCandidate {
  name: string
  mood: string
  rationale: string
  palette: PaletteShape
  layout_style?: string
  typography?: string
  cover_style?: string
  use_case?: string
}

interface Props {
  lessonId?: string
  subject?: string
  gradeLevel?: string
  region?: string
  topic?: string
  content?: string
  outlineId?: string
  autoSubmit?: boolean
  sourceRef?: SourceRef | null
}

const STYLE_TAGS = ['childish', 'academic', 'business', 'minimal', 'tech', 'natural', 'artistic'] as const
const PALETTE_ORDER: (keyof PaletteShape)[] = [
  'bg', 'section_bg', 'accent', 'title_color', 'body_color', 'bullet_color',
]

const TYPOGRAPHY_FF: Record<string, string> = {
  serif: `'Source Han Serif SC', 'Noto Serif SC', Georgia, serif`,
  sans_display: `'Microsoft YaHei UI', 'PingFang SC', system-ui, sans-serif`,
  handwriting: `'楷体', 'Kaiti SC', 'STKaiti', cursive`,
  mono: `'Consolas', 'SFMono-Regular', 'Menlo', monospace`,
}

function parseSSEFrame(raw: string): { event: string; data: any } | null {
  if (!raw) return null
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  const rawData = dataLines.join('\n')
  if (!rawData) return { event, data: {} }
  try {
    return { event, data: JSON.parse(rawData) }
  } catch {
    return { event, data: { raw: rawData } }
  }
}

/** Pure CSS 16:9 thumbnail preview for a candidate. No remote assets. */
function TemplateThumbnail({ candidate }: { candidate: StyleCandidate }) {
  const p = candidate.palette
  const ff = TYPOGRAPHY_FF[candidate.typography || 'sans_display'] || TYPOGRAPHY_FF.sans_display
  const cover = candidate.cover_style || 'centered'

  const base: React.CSSProperties = {
    position: 'relative',
    width: '100%',
    aspectRatio: '16 / 9',
    background: p.bg,
    borderRadius: 8,
    overflow: 'hidden',
    fontFamily: ff,
    boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.06)',
  }

  if (cover === 'split') {
    return (
      <div style={base}>
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: '40%',
          background: p.section_bg,
        }} />
        <div style={{
          position: 'absolute', left: '8%', top: '45%', width: '20%', height: 3,
          background: p.accent,
        }} />
        <div style={{
          position: 'absolute', left: '46%', top: '28%', right: '8%',
          color: p.title_color, fontWeight: 700, fontSize: '12%', lineHeight: 1.1,
        }}>
          {candidate.name || 'Template'}
        </div>
        <div style={{
          position: 'absolute', left: '46%', top: '52%', right: '8%',
          color: p.body_color, fontSize: '7%',
        }}>
          {candidate.mood}
        </div>
      </div>
    )
  }
  if (cover === 'decorative') {
    return (
      <div style={base}>
        <div style={{
          position: 'absolute', left: '-6%', top: '-10%', width: '22%', aspectRatio: '1/1',
          background: p.accent, borderRadius: '50%',
        }} />
        <div style={{
          position: 'absolute', right: '-4%', bottom: '-8%', width: '28%', aspectRatio: '1/1',
          background: p.accent, opacity: 0.6, borderRadius: '50%',
        }} />
        <div style={{
          position: 'absolute', right: '8%', top: '8%', width: '10%', aspectRatio: '1/1',
          background: p.bullet_color, borderRadius: '50%',
        }} />
        <div style={{
          position: 'absolute', left: '8%', right: '8%', top: '38%', textAlign: 'center',
          color: p.title_color, fontWeight: 700, fontSize: '13%', lineHeight: 1.1,
        }}>
          {candidate.name || 'Template'}
        </div>
        <div style={{
          position: 'absolute', left: '20%', right: '20%', top: '62%', textAlign: 'center',
          color: p.body_color, fontSize: '7%',
        }}>
          {candidate.mood}
        </div>
      </div>
    )
  }
  // centered (default)
  return (
    <div style={base}>
      <div style={{
        position: 'absolute', left: '8%', right: '8%', top: '28%', textAlign: 'center',
        color: p.title_color, fontWeight: 700, fontSize: '14%', lineHeight: 1.1,
      }}>
        {candidate.name || 'Template'}
      </div>
      <div style={{
        position: 'absolute', left: '38%', right: '38%', top: '52%', height: 3,
        background: p.accent,
      }} />
      <div style={{
        position: 'absolute', left: '8%', right: '8%', top: '62%', textAlign: 'center',
        color: p.body_color, fontSize: '7%',
      }}>
        {candidate.mood}
      </div>
    </div>
  )
}

export default function PPTPanel({
  lessonId, subject = '', gradeLevel = '', region = 'mainland',
  topic = '', content = '', outlineId = '', sourceRef = null,
}: Props) {
  const effectiveSource: SourceRef | null = sourceRef
    ? sourceRef
    : lessonId
      ? { kind: 'lesson', id: lessonId, title: '', mode: 'auto' }
      : outlineId
        ? { kind: 'outline', id: outlineId, title: '' }
        : null
  const t = useT()
  const [styleTags, setStyleTags] = useState<string[]>([])
  const [styleDesc, setStyleDesc] = useState('')
  const [deckTheme, setDeckTheme] = useState('')
  const [analysisText, setAnalysisText] = useState('')
  const [candidates, setCandidates] = useState<StyleCandidate[]>([])
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pptResult, setPptResult] = useState<any>(null)
  const [pptId, setPptId] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const sourceKey = effectiveSource
    ? `${effectiveSource.kind}:${effectiveSource.id}:${effectiveSource.kind === 'lesson' ? effectiveSource.mode : ''}`
    : ''

  useEffect(() => {
    if (analysisText || candidates.length) {
      setAnalysisText('')
      setCandidates([])
      setSelectedIdx(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, subject, gradeLevel, sourceKey, styleTags.join(','), styleDesc])

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  const toggleTag = (tag: string) => {
    setStyleTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])
  }

  const analyzeStyle = async () => {
    if (!topic && !subject && !effectiveSource) {
      setError(t('tools.need_topic_or_subject'))
      return
    }
    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac
    setAnalyzing(true)
    setError('')
    setAnalysisText('')
    setCandidates([])
    setSelectedIdx(null)

    try {
      const fd = new FormData()
      fd.append('subject', subject)
      fd.append('grade_level', gradeLevel)
      fd.append('region', region)
      fd.append('topic', topic)
      fd.append('style_tags', styleTags.join(','))
      fd.append('style_description', styleDesc)
      applySourceToFormData(fd, effectiveSource)

      const token = useAuthStore.getState().token
      const res = await fetch('/api/v1/course-tools/ppt/analyze-style/stream', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
        signal: ac.signal,
      })
      if (!res.ok || !res.body) {
        let detail = ''
        try {
          const maybe = await res.json()
          detail = maybe?.detail || ''
        } catch { /* ignore */ }
        throw new Error(detail || `HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let receivedFinal = false
      let streamErr = ''

      for (; ;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let sepIdx
        while ((sepIdx = buf.indexOf('\n\n')) >= 0) {
          const raw = buf.slice(0, sepIdx)
          buf = buf.slice(sepIdx + 2)
          const ev = parseSSEFrame(raw)
          if (!ev) continue
          if (ev.event === 'delta') {
            if (ev.data?.text) setAnalysisText(prev => prev + ev.data.text)
          } else if (ev.event === 'final') {
            const arr = Array.isArray(ev.data?.candidates) ? ev.data.candidates : []
            const cleaned: StyleCandidate[] = arr
              .filter((c: any) => c && c.palette)
              .slice(0, 3)
              .map((c: any) => ({
                name: c.name || '',
                mood: c.mood || '',
                rationale: c.rationale || '',
                palette: c.palette,
                layout_style: c.layout_style || 'modern',
                typography: c.typography || 'sans_display',
                cover_style: c.cover_style || 'centered',
                use_case: c.use_case || '',
              }))
            if (cleaned.length) {
              setCandidates(cleaned)
              setSelectedIdx(0)
              receivedFinal = true
            }
          } else if (ev.event === 'error') {
            streamErr = ev.data?.message || t('tools.analyze_failed')
          }
        }
      }

      if (streamErr) {
        setError(streamErr)
      } else if (!receivedFinal) {
        setError(t('tools.analysis_no_palette'))
      }
    } catch (e: any) {
      if (e?.name === 'AbortError') return
      setError(e?.message || t('tools.analyze_failed'))
    } finally {
      setAnalyzing(false)
    }
  }

  const addJob = useJobsStore((s) => s.add)
  const bindSocket = useJobsStore((s) => s.bindSocket)

  useEffect(() => {
    bindSocket()
    const s = getSocket()
    const onDone = async (payload: any) => {
      if (!payload?.result_id || payload.result_id !== pptId) return
      try {
        const r = await api.get(`/api/v1/course-tools/results/${pptId}`)
        if (r.data?.result) setPptResult(r.data.result)
      } catch { /* ignore */ }
    }
    s.on('course_tool_completed', onDone)
    return () => { s.off('course_tool_completed', onDone) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pptId])

  const selected = selectedIdx !== null ? candidates[selectedIdx] : null

  const generatePpt = async () => {
    if (!selected) {
      setError(t('tools.pick_style_first'))
      return
    }
    setLoading(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('subject', subject)
      fd.append('grade_level', gradeLevel)
      fd.append('region', region)
      fd.append('topic', topic)
      fd.append('content', content)
      applySourceToFormData(fd, effectiveSource)
      fd.append('palette', JSON.stringify(selected.palette))
      fd.append('palette_name', selected.name)
      fd.append('style', selected.layout_style || 'modern')
      fd.append('template', JSON.stringify(selected))
      if (deckTheme) fd.append('deck_theme', deckTheme)
      const res = await api.post('/api/v1/course-tools/ppt', fd)
      const rid = res.data.result_id || res.data.id
      setPptId(rid)
      setPptResult(res.data.result || null)
      addJob({ result_id: rid, tool_type: 'ppt', title: res.data.title || topic || '' })
      toast.info(t('tools.job_enqueued'))
    } catch (e: any) {
      setError(e.response?.data?.detail || t('tools.gen_failed'))
    } finally {
      setLoading(false)
    }
  }

  const download = async () => {
    try {
      const res = await api.get(`/api/v1/course-tools/ppt/${pptId}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const match = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'ppt.pptx'
      const a = document.createElement('a')
      a.href = url
      a.download = fname
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setError(t('tools.download_failed'))
    }
  }

  const previewHtml = async () => {
    try {
      const res = await api.get(`/api/v1/course-tools/ppt/${pptId}/preview`, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      setError(t('tools.preview_failed'))
    }
  }

  const downloadHtml = async () => {
    try {
      const res = await api.get(`/api/v1/course-tools/ppt/${pptId}/download-html`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const match = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'ppt.html'
      const a = document.createElement('a')
      a.href = url
      a.download = fname
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setError(t('tools.download_failed'))
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
      )}

      <div>
        <p className="text-sm text-gray-600 mb-2">{t('tools.ppt_style_tags_label')}</p>
        <div className="flex flex-wrap gap-2">
          {STYLE_TAGS.map(tag => {
            const active = styleTags.includes(tag)
            return (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                  active
                    ? 'bg-brand-600 text-white border-brand-600 shadow-sm'
                    : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400 hover:text-brand-600'
                }`}
              >
                {t(`tools.tag_${tag}`)}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="text-sm text-gray-600 mb-2">{t('tools.ppt_style_desc_label')}</p>
        <textarea
          className="w-full rounded-lg border border-gray-200 p-2.5 text-sm resize-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          rows={2}
          placeholder={t('tools.ppt_style_desc_placeholder')}
          value={styleDesc}
          onChange={e => setStyleDesc(e.target.value)}
        />
      </div>

      <div>
        <p className="text-sm text-gray-600 mb-2">{t('tools.deck_theme_label')}</p>
        <select
          className="w-full rounded-lg border border-gray-200 p-2.5 text-sm bg-white focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          value={deckTheme}
          onChange={e => setDeckTheme(e.target.value)}
        >
          <option value="">{t('tools.deck_theme_default')}</option>
          <option value="ink_classic">{t('tools.deck_theme_ink')}</option>
          <option value="swiss_ikb">{t('tools.deck_theme_swiss')}</option>
          <option value="ink_indigo">电子墨水 · 靛蓝瓷</option>
          <option value="swiss_orange">瑞士风 · 安全橙</option>
        </select>
        <p className="text-[11px] text-gray-400 mt-1">{t('tools.deck_theme_hint')}</p>
      </div>

      <Button
        variant={candidates.length ? 'secondary' : 'primary'}
        onClick={analyzeStyle}
        disabled={analyzing}
        className="w-full"
      >
        {analyzing
          ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />{t('tools.analyzing_style')}</>
          : candidates.length
            ? <><RefreshCw className="w-4 h-4 mr-2" />{t('tools.re_analyze')}</>
            : <><Palette className="w-4 h-4 mr-2" />{t('tools.analyze_style')}</>}
      </Button>

      {(analyzing || analysisText) && (
        <div className="rounded-xl border border-brand-100 bg-gradient-to-br from-brand-50/60 to-white p-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-4 h-4 text-brand-600" />
            <span className="text-sm font-medium text-gray-700">
              {analyzing ? t('tools.analyzing_style') : t('tools.analysis_result')}
            </span>
          </div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {analysisText}
            {analyzing && (
              <span className="inline-block w-2 h-4 bg-brand-500 animate-pulse align-middle ml-0.5" />
            )}
          </div>
        </div>
      )}

      {candidates.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-brand-600" />
            <span className="text-sm font-medium text-gray-700">
              {t('tools.template_candidates')}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {candidates.map((c, idx) => {
              const active = selectedIdx === idx
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedIdx(idx)}
                  className={`relative text-left rounded-xl border p-3 bg-white transition-all ${
                    active
                      ? 'border-brand-500 ring-2 ring-brand-500 shadow-md'
                      : 'border-gray-200 hover:border-brand-300 hover:shadow-sm'
                  }`}
                >
                  {active && (
                    <span className="absolute top-2 right-2 w-6 h-6 rounded-full bg-brand-600 text-white flex items-center justify-center shadow">
                      <Check className="w-3.5 h-3.5" />
                    </span>
                  )}
                  <TemplateThumbnail candidate={c} />
                  <div className="mt-2.5">
                    <div className="text-sm font-semibold text-gray-800">{c.name}</div>
                    <div className="text-[11px] text-gray-500 mt-0.5">{c.mood}</div>
                  </div>
                  <div className="flex h-6 rounded-md overflow-hidden border border-gray-100 mt-2">
                    {PALETTE_ORDER.map(key => (
                      <div
                        key={key}
                        className="flex-1"
                        style={{ backgroundColor: c.palette[key] }}
                        title={`${key}: ${c.palette[key]}`}
                      />
                    ))}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {c.layout_style && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                        {t('tools.layout_style_label')}: {c.layout_style}
                      </span>
                    )}
                    {c.typography && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                        {t('tools.typography_label')}: {c.typography}
                      </span>
                    )}
                    {c.cover_style && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                        {t('tools.cover_style_label')}: {c.cover_style}
                      </span>
                    )}
                  </div>
                  {c.use_case && (
                    <p className="text-[11px] text-gray-500 mt-2">
                      <span className="font-medium text-gray-600">{t('tools.use_case_label')}:</span> {c.use_case}
                    </p>
                  )}
                  {c.rationale && (
                    <p className="text-[11px] text-gray-500 mt-1 leading-relaxed line-clamp-3">{c.rationale}</p>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <Button
        onClick={generatePpt}
        disabled={loading || !selected}
        className="w-full"
      >
        {loading
          ? <Loader2 className="w-4 h-4 animate-spin mr-2" />
          : <Sparkles className="w-4 h-4 mr-2" />}
        {t('tools.confirm_generate_ppt')}
      </Button>

      {pptResult && (
        <div className="mt-4 space-y-3">
          <h3 className="font-medium text-gray-800">{pptResult.title}</h3>
          <div className="grid grid-cols-3 gap-3 max-h-96 overflow-y-auto">
            {(pptResult.slides || []).map((slide: any, i: number) => (
              <div key={i} className={`rounded-lg p-3 text-xs border ${
                slide.layout === 'title_slide' ? 'bg-brand-50 border-brand-200' :
                slide.layout === 'section_header' ? 'bg-purple-50 border-purple-200' :
                slide.layout === 'closing' ? 'bg-green-50 border-green-200' :
                'bg-gray-50 border-gray-200'
              }`}>
                <div className="font-medium text-gray-800 mb-1">#{i + 1} {slide.title}</div>
                {slide.bullets?.slice(0, 3).map((b: string, j: number) => (
                  <div key={j} className="text-gray-500 truncate">• {b}</div>
                ))}
                {(slide.bullets?.length || 0) > 3 && <div className="text-gray-400">...</div>}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={previewHtml}>
              <Eye className="w-4 h-4 mr-2" />{t('tools.preview_html')}
            </Button>
            <Button variant="secondary" onClick={download}>
              <Download className="w-4 h-4 mr-2" />{t('tools.download_pptx')}
            </Button>
            <Button variant="secondary" onClick={downloadHtml}>
              <Code2 className="w-4 h-4 mr-2" />{t('tools.download_html')}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
