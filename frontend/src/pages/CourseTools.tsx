import { useState, useEffect } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import SourcePicker, { SourceRef, applySourceToFormData } from '../components/course/SourcePicker'
import { useJobsStore } from '../stores/jobsStore'
import { toast } from '../components/ui/Toast'
import { getSocket } from '../services/socket'
import {
  FileText, Presentation, ClipboardList, FlaskConical,
  Download, Loader2, Sparkles, Merge, Palette, RefreshCw, Check, Image, Eye, Layers,
} from 'lucide-react'

type Tab = 'outline' | 'ppt' | 'exercises' | 'practice' | 'comic' | 'cards'

interface HistoryItem {
  id: string; tool_type: string; title: string; created_at: string; params: Record<string, any>
}

interface PaletteShape {
  bg: string; title_color: string; body_color: string
  accent: string; section_bg: string; bullet_color: string
}

interface StyleCandidate {
  name: string; mood: string; rationale: string; palette: PaletteShape
}

const TABS: { key: Tab; icon: typeof FileText; labelKey: string }[] = [
  { key: 'outline', icon: FileText, labelKey: 'tools.tab_outline' },
  { key: 'ppt', icon: Presentation, labelKey: 'tools.tab_ppt' },
  { key: 'exercises', icon: ClipboardList, labelKey: 'tools.tab_exercises' },
  { key: 'practice', icon: FlaskConical, labelKey: 'tools.tab_practice' },
  { key: 'comic', icon: Image, labelKey: 'tools.tab_comic' },
  { key: 'cards', icon: Layers, labelKey: 'tools.tab_cards' },
]

const STYLE_TAGS = ['childish', 'academic', 'business', 'minimal', 'tech', 'natural', 'artistic'] as const
const PALETTE_ORDER: (keyof PaletteShape)[] = ['bg', 'section_bg', 'accent', 'title_color', 'body_color', 'bullet_color']

export default function CourseTools() {
  const { lessonId } = useParams<{ lessonId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const t = useT()
  const urlTab = (searchParams.get('tab') as Tab) || 'outline'
  const urlResultId = searchParams.get('result_id') || ''
  const forUserId = searchParams.get('for_user_id') || ''
  const scopeParams = forUserId ? { for_user_id: forUserId } : undefined
  const [tab, _setTab] = useState<Tab>(urlTab)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])
  const addJob = useJobsStore((s) => s.add)
  const bindSocket = useJobsStore((s) => s.bindSocket)

  // keep URL in sync when tab changes
  const setTab = (next: Tab) => {
    _setTab(next)
    const sp = new URLSearchParams(searchParams)
    sp.set('tab', next)
    setSearchParams(sp, { replace: true })
  }

  // shared fields
  const [subject, setSubject] = useState('')
  const [gradeLevel, setGradeLevel] = useState('')
  const [region, setRegion] = useState('mainland')
  const [topic, setTopic] = useState('')
  const [content, setContent] = useState('')

  // unified source: lesson / series / outline
  const [source, setSource] = useState<SourceRef | null>(
    lessonId ? { kind: 'lesson', id: lessonId, title: lessonId, mode: 'auto' } : null
  )

  // outline
  const [scope, setScope] = useState<'semester' | 'single_lesson'>('single_lesson')
  const [outlineResult, setOutlineResult] = useState<any>(null)
  const [outlineId, setOutlineId] = useState('')

  // ppt
  const [pptResult, setPptResult] = useState<any>(null)
  const [pptId, setPptId] = useState('')
  const [styleTags, setStyleTags] = useState<string[]>([])
  const [styleDesc, setStyleDesc] = useState('')
  const [styleCandidates, setStyleCandidates] = useState<StyleCandidate[]>([])
  const [selectedStyle, setSelectedStyle] = useState<StyleCandidate | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  // Reset candidates + clear stale error banner when key fields change.
  // 避免上一次失败/中途断网留下的红条一直挂着，让用户误以为"风格分析失败"。
  useEffect(() => {
    if (styleCandidates.length || selectedStyle) {
      setStyleCandidates([])
      setSelectedStyle(null)
    }
    if (error) setError('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, subject, gradeLevel, styleTags.join(','), styleDesc, source])

  // Switching tabs should clear stale error banners as well.
  useEffect(() => {
    if (error) setError('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  const toggleTag = (tag: string) => {
    setStyleTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])
  }

  const analyzeStyle = async () => {
    if (!topic && !subject && !source) {
      setError(t('tools.need_topic_or_subject'))
      return
    }
    setAnalyzing(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('subject', subject)
      fd.append('grade_level', gradeLevel)
      fd.append('region', region)
      fd.append('topic', topic)
      fd.append('style_tags', styleTags.join(','))
      fd.append('style_description', styleDesc)
      applySourceToFormData(fd, source)
      const res = await api.post('/api/v1/course-tools/ppt/analyze-style', fd)
      const raw = Array.isArray(res?.data?.candidates) ? res.data.candidates : []
      const list: StyleCandidate[] = raw
        .filter((c: any) => c && c.palette)
        .map((c: any) => ({
          name: String(c.name || '候选方案'),
          mood: String(c.mood || ''),
          rationale: String(c.rationale || ''),
          palette: c.palette,
        }))
      if (!list.length) {
        // 200 OK 但 AI 没给合法候选 —— 让用户看到"AI 没返回"，而不是无声失败
        setError(t('tools.analysis_no_palette') || 'AI 没返回合法的配色方案，请重试')
        return
      }
      setStyleCandidates(list)
      setSelectedStyle(list[0])
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      const msg = typeof detail === 'string' && detail
        ? detail
        : (e?.message || t('tools.analyze_failed'))
      // eslint-disable-next-line no-console
      console.warn('[analyzeStyle] failed:', e)
      setError(msg)
    } finally {
      setAnalyzing(false)
    }
  }

  // exercises
  const [exType, setExType] = useState('daily_homework')
  const [exDiff, setExDiff] = useState('medium')
  const [exCount, setExCount] = useState(10)
  const [exResult, setExResult] = useState<any>(null)
  const [exId, setExId] = useState('')

  // practice
  const [includeTheory, setIncludeTheory] = useState(true)
  const [practiceResult, setPracticeResult] = useState<any>(null)
  const [practiceId, setPracticeId] = useState('')

  // comic 知识漫画
  const [comicResult, setComicResult] = useState<any>(null)
  const [comicId, setComicId] = useState('')
  const [comicArt, setComicArt] = useState('ligne-claire')
  const [comicTone, setComicTone] = useState('warm')
  const [comicLayout, setComicLayout] = useState('standard')
  const [comicAspect, setComicAspect] = useState('3:4')
  const [comicWithImages, setComicWithImages] = useState(true)

  // cards 英语学习卡片
  const [cardsResult, setCardsResult] = useState<any>(null)
  const [cardsId, setCardsId] = useState('')
  const [cardsTheme, setCardsTheme] = useState('minimal')
  const [cardsAspect, setCardsAspect] = useState('3:4')
  const [cardsCount, setCardsCount] = useState(10)
  const [cardsWithImages, setCardsWithImages] = useState(true)

  useEffect(() => {
    const lid = source?.kind === 'lesson' ? source.id : lessonId
    api.get('/api/v1/course-tools/history', { params: { lesson_id: lid || undefined, ...(scopeParams || {}) } })
      .then(r => setHistory(r.data))
      .catch(() => {})
  }, [lessonId, source, outlineId, pptId, exId, practiceId, forUserId])

  // Hydrate an existing result when URL carries ?result_id=
  useEffect(() => {
    if (!urlResultId) return
    api.get(`/api/v1/course-tools/results/${urlResultId}`, { params: scopeParams })
      .then(r => {
        const d = r.data
        const type = d.tool_type as Tab
        _setTab(type)
        if (d.status !== 'completed') {
          // nothing to populate yet; socket will fill later
          return
        }
        switch (type) {
          case 'outline':
            setOutlineResult(d.result); setOutlineId(d.id); break
          case 'ppt':
            setPptResult(d.result); setPptId(d.id); break
          case 'exercises':
            setExResult(d.result); setExId(d.id); break
          case 'practice':
            setPracticeResult(d.result); setPracticeId(d.id); break
          case 'comic':
            setComicResult(d.result); setComicId(d.id); break
          case 'cards':
            setCardsResult(d.result); setCardsId(d.id); break
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlResultId, forUserId])

  // Listen for socket completion events that match our pending result_ids
  useEffect(() => {
    bindSocket()
    const s = getSocket()
    const onDone = async (payload: any) => {
      const rid = payload?.result_id
      if (!rid) return
      try {
        const r = await api.get(`/api/v1/course-tools/results/${rid}`, { params: scopeParams })
        const d = r.data
        const type = d.tool_type as Tab
        // Only populate into visible tab if the tab matches
        switch (type) {
          case 'outline':
            if (outlineId === rid || !outlineId) { setOutlineResult(d.result); setOutlineId(d.id) } break
          case 'ppt':
            if (pptId === rid || !pptId) { setPptResult(d.result); setPptId(d.id) } break
          case 'exercises':
            if (exId === rid || !exId) { setExResult(d.result); setExId(d.id) } break
          case 'practice':
            if (practiceId === rid || !practiceId) { setPracticeResult(d.result); setPracticeId(d.id) } break
          case 'comic':
            if (comicId === rid || !comicId) { setComicResult(d.result); setComicId(d.id) } break
          case 'cards':
            if (cardsId === rid || !cardsId) { setCardsResult(d.result); setCardsId(d.id) } break
        }
      } catch {}
    }
    s.on('course_tool_completed', onDone)
    return () => { s.off('course_tool_completed', onDone) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outlineId, pptId, exId, practiceId, forUserId])

  const formData = (extra: Record<string, any>) => {
    const fd = new FormData()
    fd.append('subject', subject)
    fd.append('grade_level', gradeLevel)
    fd.append('region', region)
    fd.append('topic', topic)
    fd.append('content', content)
    applySourceToFormData(fd, source)
    Object.entries(extra).forEach(([k, v]) => {
      if (v === '' || v === null || v === undefined) return
      fd.append(k, String(v))
    })
    return fd
  }

  const generate = async (
    endpoint: string,
    extra: Record<string, any>,
    _onSuccess: (d: any) => void,
  ) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post(`/api/v1/course-tools/${endpoint}`, formData(extra))
      const d = res.data
      const toolType = (d.tool_type as 'outline' | 'ppt' | 'exercises' | 'practice' | 'comic' | 'cards') ||
        ((['outline', 'ppt', 'exercises', 'practice', 'comic', 'cards'] as const).find(x => endpoint.startsWith(x))) ||
        'outline'
      // remember pending result id in the same slot so socket completion can fill it later
      switch (toolType) {
        case 'outline': setOutlineId(d.result_id || d.id); break
        case 'ppt': setPptId(d.result_id || d.id); break
        case 'exercises': setExId(d.result_id || d.id); break
        case 'practice': setPracticeId(d.result_id || d.id); break
        case 'comic': setComicId(d.result_id || d.id); break
        case 'cards': setCardsId(d.result_id || d.id); break
      }
      addJob({
        result_id: d.result_id || d.id,
        tool_type: toolType,
        title: d.title || '',
        status: (d.status as any) || 'queued',
      })
      toast.info(t('tools.job_enqueued'))
    } catch (e: any) {
      setError(e.response?.data?.detail || t('tools.gen_failed'))
      toast.error(e.response?.data?.detail || t('tools.gen_failed'))
    } finally {
      setLoading(false)
    }
  }

  const download = (endpoint: string) => {
    const token = (window as any).__auth_token || ''
    const a = document.createElement('a')
    a.href = `/api/v1/course-tools/${endpoint}`
    a.click()
  }

  const previewInNewTab = async (endpoint: string) => {
    try {
      const res = await api.get(`/api/v1/course-tools/${endpoint}`, { params: scopeParams, responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      setError(t('tools.preview_failed'))
    }
  }

  const downloadWithAuth = async (endpoint: string) => {
    try {
      const res = await api.get(`/api/v1/course-tools/${endpoint}`, { params: scopeParams, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const match = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'download'
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
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
          <Link to="/dashboard" className="hover:text-brand-600">{t('tools.dashboard')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('tools.title')}</span>
        </div>

        <div className="flex gap-6">
          {/* ── Left panel ── */}
          <div className="w-72 flex-shrink-0 space-y-4">
            {/* Unified source picker */}
            <SourcePicker value={source} onChange={setSource} />

            {/* Quick input */}
            <div className="bg-white rounded-xl border p-4 space-y-3">
              <h3 className="text-sm font-medium text-gray-700">{t('tools.quick_input')}</h3>
              <Input placeholder={t('tools.subject_ph')} value={subject} onChange={e => setSubject(e.target.value)} />
              <Input placeholder={t('tools.grade_ph')} value={gradeLevel} onChange={e => setGradeLevel(e.target.value)} />
              <Input placeholder={t('tools.topic_ph')} value={topic} onChange={e => setTopic(e.target.value)} />
              <textarea
                className="w-full rounded-lg border border-gray-200 p-2.5 text-sm resize-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                rows={4}
                placeholder={t('tools.content_ph')}
                value={content}
                onChange={e => setContent(e.target.value)}
              />
            </div>

            {/* History */}
            <div className="bg-white rounded-xl border p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">{t('tools.history')}</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {history.length === 0 && <p className="text-xs text-gray-400">{t('tools.no_history')}</p>}
                {history.map(h => (
                  <div key={h.id} className="flex items-center gap-2 text-xs p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                    onClick={() => {
                      _setTab(h.tool_type as Tab)
                      const sp = new URLSearchParams(searchParams)
                      sp.set('tab', h.tool_type)
                      sp.set('result_id', h.id)
                      setSearchParams(sp, { replace: true })
                    }}>
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      h.tool_type === 'outline' ? 'bg-blue-500' :
                      h.tool_type === 'ppt' ? 'bg-purple-500' :
                      h.tool_type === 'exercises' ? 'bg-green-500' : 'bg-orange-500'
                    }`} />
                    <span className="truncate flex-1 text-gray-700">{h.title || h.tool_type}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Right content ── */}
          <div className="flex-1 min-w-0">
            {/* Tabs */}
            <div className="flex gap-1 bg-white rounded-xl border p-1 mb-6">
              {TABS.map(tb => {
                const Icon = tb.icon
                const active = tab === tb.key
                return (
                  <button key={tb.key} onClick={() => setTab(tb.key)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active ? 'bg-brand-600 text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                    }`}>
                    <Icon className="w-4 h-4" />
                    {t(tb.labelKey)}
                  </button>
                )
              })}
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-start gap-2">
                <span className="flex-1">{error}</span>
                <button
                  type="button"
                  className="text-red-400 hover:text-red-600 font-semibold leading-none px-1"
                  onClick={() => setError('')}
                  aria-label="dismiss"
                >
                  ×
                </button>
              </div>
            )}

            {/* ── Outline Tab ── */}
            {tab === 'outline' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.outline_title')}</h2>
                <div className="flex gap-3">
                  {(['single_lesson', 'semester'] as const).map(s => (
                    <button key={s} onClick={() => setScope(s)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        scope === s ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}>
                      {s === 'single_lesson' ? t('tools.scope_lesson') : t('tools.scope_semester')}
                    </button>
                  ))}
                </div>
                <Button onClick={() => generate('outline', { scope }, d => { setOutlineResult(d.result); setOutlineId(d.id) })}
                  disabled={loading} className="w-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  {t('tools.generate')}
                </Button>
                {outlineResult && (
                  <div className="mt-4 space-y-3">
                    <h3 className="font-medium text-gray-800">{outlineResult.title}</h3>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {(outlineResult.sections || []).map((sec: any, i: number) => (
                        <div key={i} className="border rounded-lg p-3">
                          <div className="font-medium text-sm text-gray-800">{sec.title}</div>
                          {sec.duration && <div className="text-xs text-gray-500 mt-1">{sec.duration}</div>}
                          {sec.key_points?.map((kp: string, j: number) => (
                            <div key={j} className="text-xs text-gray-600 mt-1 pl-3">• {kp}</div>
                          ))}
                        </div>
                      ))}
                    </div>
                    <Button variant="secondary" onClick={() => downloadWithAuth(`outline/${outlineId}/download`)}>
                      <Download className="w-4 h-4 mr-2" />{t('tools.download_docx')}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* ── PPT Tab ── */}
            {tab === 'ppt' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.ppt_title')}</h2>

                {/* Style tag pills */}
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

                {/* Free-form description */}
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

                {/* Analyze button */}
                <Button
                  variant={styleCandidates.length ? 'secondary' : 'primary'}
                  onClick={analyzeStyle}
                  disabled={analyzing}
                  className="w-full"
                >
                  {analyzing
                    ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />{t('tools.analyzing')}</>
                    : styleCandidates.length
                      ? <><RefreshCw className="w-4 h-4 mr-2" />{t('tools.re_analyze')}</>
                      : <><Palette className="w-4 h-4 mr-2" />{t('tools.analyze_style')}</>}
                </Button>

                {/* Candidate cards */}
                {styleCandidates.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-gray-700">{t('tools.style_candidates')}</p>
                    <div className="grid grid-cols-3 gap-3">
                      {styleCandidates.map((c, idx) => {
                        const active = selectedStyle?.name === c.name && selectedStyle?.rationale === c.rationale
                        return (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setSelectedStyle(c)}
                            className={`text-left rounded-xl border p-3 bg-white transition-all hover:shadow-md ${
                              active ? 'ring-2 ring-brand-500 border-brand-400' : 'border-gray-200'
                            }`}
                          >
                            {/* 6-color bar */}
                            <div className="flex h-10 rounded-md overflow-hidden mb-2 border border-gray-100">
                              {PALETTE_ORDER.map(key => (
                                <div key={key} className="flex-1" style={{ backgroundColor: c.palette[key] }} />
                              ))}
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-sm text-gray-800 truncate">{c.name}</span>
                              {active && <Check className="w-4 h-4 text-brand-600 flex-shrink-0" />}
                            </div>
                            <div className="text-xs text-gray-500 mt-0.5 truncate">{c.mood}</div>
                            <div className="text-[11px] text-gray-400 mt-1.5 leading-snug line-clamp-3">
                              {c.rationale}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

                {outlineId && (
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" defaultChecked className="rounded" />
                    {t('tools.ppt_use_outline')}
                  </label>
                )}

                {/* Generate PPT (only when a style is picked) */}
                <Button
                  onClick={() => {
                    if (!selectedStyle) {
                      setError(t('tools.pick_style_first'))
                      return
                    }
                    generate('ppt', {
                      palette: JSON.stringify(selectedStyle.palette),
                      palette_name: selectedStyle.name,
                      outline_id: outlineId || '',
                    }, d => { setPptResult(d.result); setPptId(d.id) })
                  }}
                  disabled={loading || !selectedStyle}
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
                    <Button variant="secondary" onClick={() => downloadWithAuth(`ppt/${pptId}/download`)}>
                      <Download className="w-4 h-4 mr-2" />{t('tools.download_pptx')}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* ── Exercises Tab ── */}
            {tab === 'exercises' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.exercises_title')}</h2>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { v: 'daily_homework', k: 'tools.ex_homework' },
                    { v: 'quiz', k: 'tools.ex_quiz' },
                    { v: 'exam', k: 'tools.ex_exam' },
                  ].map(o => (
                    <button key={o.v} onClick={() => setExType(o.v)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        exType === o.v ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}>{t(o.k)}</button>
                  ))}
                </div>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.difficulty')}</label>
                    <select value={exDiff} onChange={e => setExDiff(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="easy">{t('tools.diff_easy')}</option>
                      <option value="medium">{t('tools.diff_medium')}</option>
                      <option value="hard">{t('tools.diff_hard')}</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.count')}</label>
                    <input type="number" min={1} max={50} value={exCount} onChange={e => setExCount(+e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm" />
                  </div>
                </div>
                <Button onClick={() => generate('exercises', { exercise_type: exType, difficulty: exDiff, count: exCount, ppt_id: pptId || '' },
                  d => { setExResult(d.result); setExId(d.id) })} disabled={loading} className="w-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  {t('tools.generate_exercises')}
                </Button>
                {exResult && (
                  <div className="mt-4 space-y-3">
                    <h3 className="font-medium text-gray-800">{exResult.title}</h3>
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {(exResult.exercises || []).map((ex: any, i: number) => (
                        <div key={`ex-${i}-${ex.id ?? ''}`} className="border rounded-lg p-3">
                          <div className="text-sm font-medium text-gray-800">{ex.id ?? i + 1}. {ex.question}</div>
                          {ex.options?.map((opt: string, j: number) => (
                            <div key={j} className="text-xs text-gray-600 mt-1 pl-3">{opt}</div>
                          ))}
                          <div className="mt-2 flex gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              ex.difficulty === 'easy' ? 'bg-green-100 text-green-700' :
                              ex.difficulty === 'hard' ? 'bg-red-100 text-red-700' :
                              'bg-yellow-100 text-yellow-700'
                            }`}>{ex.difficulty}</span>
                            <span className="text-xs text-gray-400">{ex.score}{t('tools.score_unit')}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-3">
                      <Button variant="secondary" onClick={() => downloadWithAuth(`exercises/${exId}/download?version=student`)}>
                        <Download className="w-4 h-4 mr-2" />{t('tools.download_student')}
                      </Button>
                      <Button variant="secondary" onClick={() => downloadWithAuth(`exercises/${exId}/download?version=teacher`)}>
                        <Download className="w-4 h-4 mr-2" />{t('tools.download_teacher')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Practice Tab ── */}
            {tab === 'practice' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.practice_title')}</h2>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={includeTheory} onChange={e => setIncludeTheory(e.target.checked)} className="rounded" />
                  {t('tools.include_theory')}
                </label>
                <Button onClick={() => generate('practice', { include_theory: includeTheory, outline_id: outlineId || '' },
                  d => { setPracticeResult(d.result); setPracticeId(d.id) })} disabled={loading} className="w-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  {t('tools.generate_practice')}
                </Button>
                {practiceResult && (
                  <div className="mt-4 space-y-3">
                    <h3 className="font-medium text-gray-800">{practiceResult.title}</h3>
                    {practiceResult.theory_summary && (
                      <div className="bg-blue-50 rounded-lg p-4">
                        <div className="text-sm font-medium text-blue-800 mb-1">{t('tools.theory_summary')}</div>
                        <div className="text-sm text-blue-700">{practiceResult.theory_summary}</div>
                      </div>
                    )}
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                      {(practiceResult.practices || []).map((p: any, i: number) => (
                        <div key={`pr-${i}-${p.id ?? ''}`} className="border rounded-lg p-3">
                          <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              p.type === 'hands_on' ? 'bg-orange-100 text-orange-700' :
                              p.type === 'group' ? 'bg-purple-100 text-purple-700' :
                              p.type === 'discussion' ? 'bg-teal-100 text-teal-700' :
                              'bg-blue-100 text-blue-700'
                            }`}>{p.type}</span>
                            <span className="text-sm font-medium text-gray-800">{p.title}</span>
                          </div>
                          <p className="text-xs text-gray-600 mt-1">{p.description}</p>
                          {p.duration && <p className="text-xs text-gray-400 mt-1">{p.duration}</p>}
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-3 flex-wrap">
                      <Button variant="secondary" onClick={() => downloadWithAuth(`practice/${practiceId}/download`)}>
                        <Download className="w-4 h-4 mr-2" />{t('tools.download_docx')}
                      </Button>
                      {pptId && (
                        <Button variant="secondary" onClick={async () => {
                          setLoading(true)
                          try {
                            const fd = new FormData()
                            fd.append('ppt_id', pptId)
                            const res = await api.post(`/api/v1/course-tools/practice/${practiceId}/merge-ppt`, fd, {
                              params: scopeParams,
                            })
                            setPptId(res.data.id)
                            setError('')
                            toast.success(t('tools.merge_success'))
                          } catch (e: any) {
                            setError(e.response?.data?.detail || t('tools.merge_failed'))
                          } finally {
                            setLoading(false)
                          }
                        }}>
                          <Merge className="w-4 h-4 mr-2" />{t('tools.merge_to_ppt')}
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Comic Tab 知识漫画 ── */}
            {tab === 'comic' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.comic_title')}</h2>
                <p className="text-sm text-gray-500">{t('tools.comic_desc')}</p>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.comic_art')}</label>
                    <select value={comicArt} onChange={e => setComicArt(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="ligne-claire">{t('tools.comic_art_ligne')}</option>
                      <option value="manga">{t('tools.comic_art_manga')}</option>
                      <option value="ink-brush">{t('tools.comic_art_ink')}</option>
                      <option value="chalk">{t('tools.comic_art_chalk')}</option>
                      <option value="realistic">{t('tools.comic_art_realistic')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.comic_tone')}</label>
                    <select value={comicTone} onChange={e => setComicTone(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="warm">{t('tools.comic_tone_warm')}</option>
                      <option value="neutral">{t('tools.comic_tone_neutral')}</option>
                      <option value="energetic">{t('tools.comic_tone_energetic')}</option>
                      <option value="dramatic">{t('tools.comic_tone_dramatic')}</option>
                      <option value="vintage">{t('tools.comic_tone_vintage')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.comic_layout')}</label>
                    <select value={comicLayout} onChange={e => setComicLayout(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="standard">{t('tools.comic_layout_standard')}</option>
                      <option value="cinematic">{t('tools.comic_layout_cinematic')}</option>
                      <option value="dense">{t('tools.comic_layout_dense')}</option>
                      <option value="webtoon">{t('tools.comic_layout_webtoon')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.comic_aspect')}</label>
                    <select value={comicAspect} onChange={e => setComicAspect(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="3:4">3:4</option>
                      <option value="4:3">4:3</option>
                      <option value="16:9">16:9</option>
                    </select>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
                  <input type="checkbox" checked={comicWithImages}
                    onChange={e => setComicWithImages(e.target.checked)} className="rounded" />
                  {t('tools.with_images')}
                </label>
                <Button onClick={() => generate('comic', {
                  art: comicArt, tone: comicTone, layout: comicLayout, aspect: comicAspect, lang: 'zh',
                  with_images: comicWithImages,
                }, d => { setComicResult(d.result); setComicId(d.id) })} disabled={loading} className="w-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  {t('tools.generate_comic')}
                </Button>
                {comicResult && (
                  <div className="mt-4 space-y-3">
                    <h3 className="font-medium text-gray-800">{comicResult.title}</h3>
                    {comicResult.summary && <p className="text-sm text-gray-500">{comicResult.summary}</p>}
                    <div className="text-xs text-gray-500">
                      {t('tools.comic_pages_label')}: {(comicResult.pages || []).length}
                    </div>
                    <div className="flex gap-3 flex-wrap">
                      <Button onClick={() => previewInNewTab(`comic/${comicId}/preview`)}>
                        <Eye className="w-4 h-4 mr-2" />{t('tools.preview_html')}
                      </Button>
                      <Button variant="secondary" onClick={() => downloadWithAuth(`comic/${comicId}/download-html`)}>
                        <Download className="w-4 h-4 mr-2" />{t('tools.download_html')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Cards Tab 英语卡片 ── */}
            {tab === 'cards' && (
              <div className="bg-white rounded-xl border p-6 space-y-5">
                <h2 className="text-lg font-semibold">{t('tools.cards_title')}</h2>
                <p className="text-sm text-gray-500">{t('tools.cards_desc')}</p>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.cards_theme')}</label>
                    <select value={cardsTheme} onChange={e => setCardsTheme(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="minimal">{t('tools.cards_theme_minimal')}</option>
                      <option value="kawaii">{t('tools.cards_theme_kawaii')}</option>
                      <option value="kraft">{t('tools.cards_theme_kraft')}</option>
                      <option value="sky">{t('tools.cards_theme_sky')}</option>
                      <option value="dark">{t('tools.cards_theme_dark')}</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.cards_aspect')}</label>
                    <select value={cardsAspect} onChange={e => setCardsAspect(e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm">
                      <option value="3:4">3:4</option>
                      <option value="1:1">1:1</option>
                      <option value="4:3">4:3</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm text-gray-600 block mb-1">{t('tools.cards_count')}</label>
                    <input type="number" min={4} max={30} value={cardsCount} onChange={e => setCardsCount(+e.target.value)}
                      className="w-full rounded-lg border border-gray-200 p-2 text-sm" />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
                  <input type="checkbox" checked={cardsWithImages}
                    onChange={e => setCardsWithImages(e.target.checked)} className="rounded" />
                  {t('tools.with_images')}
                </label>
                <Button onClick={() => generate('cards', {
                  theme: cardsTheme, aspect: cardsAspect, count: cardsCount, lang: 'en',
                  with_images: cardsWithImages,
                }, d => { setCardsResult(d.result); setCardsId(d.id) })} disabled={loading} className="w-full">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                  {t('tools.generate_cards')}
                </Button>
                {cardsResult && (
                  <div className="mt-4 space-y-3">
                    <h3 className="font-medium text-gray-800">{cardsResult.title}</h3>
                    <div className="text-xs text-gray-500">
                      {t('tools.cards_count_label')}: {(cardsResult.cards || []).length}
                    </div>
                    <div className="flex gap-3 flex-wrap">
                      <Button onClick={() => previewInNewTab(`cards/${cardsId}/preview`)}>
                        <Eye className="w-4 h-4 mr-2" />{t('tools.preview_html')}
                      </Button>
                      <Button variant="secondary" onClick={() => downloadWithAuth(`cards/${cardsId}/download-html`)}>
                        <Download className="w-4 h-4 mr-2" />{t('tools.download_html')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
