import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import {
  FileText, Presentation, ClipboardList, FlaskConical,
  Download, Loader2, ChevronLeft, Sparkles, Merge, BookOpen, Palette, RefreshCw, Check,
} from 'lucide-react'

type Tab = 'outline' | 'ppt' | 'exercises' | 'practice'

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
]

const STYLE_TAGS = ['childish', 'academic', 'business', 'minimal', 'tech', 'natural', 'artistic'] as const
const PALETTE_ORDER: (keyof PaletteShape)[] = ['bg', 'section_bg', 'accent', 'title_color', 'body_color', 'bullet_color']

export default function CourseTools() {
  const { lessonId } = useParams<{ lessonId: string }>()
  const t = useT()
  const [tab, setTab] = useState<Tab>('outline')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<HistoryItem[]>([])

  // shared fields
  const [subject, setSubject] = useState('')
  const [gradeLevel, setGradeLevel] = useState('')
  const [region, setRegion] = useState('mainland')
  const [topic, setTopic] = useState('')
  const [content, setContent] = useState('')

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

  // Reset candidates when key fields change so a stale palette isn't accidentally used
  useEffect(() => {
    if (styleCandidates.length || selectedStyle) {
      setStyleCandidates([])
      setSelectedStyle(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, subject, gradeLevel, styleTags.join(','), styleDesc])

  const toggleTag = (tag: string) => {
    setStyleTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])
  }

  const analyzeStyle = async () => {
    if (!topic && !subject) {
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
      if (lessonId) fd.append('lesson_id', lessonId)
      const res = await api.post('/api/v1/course-tools/ppt/analyze-style', fd)
      const list: StyleCandidate[] = res.data.candidates || []
      setStyleCandidates(list)
      setSelectedStyle(list[0] || null)
    } catch (e: any) {
      setError(e.response?.data?.detail || t('tools.analyze_failed'))
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

  useEffect(() => {
    api.get('/api/v1/course-tools/history', { params: { lesson_id: lessonId || undefined } })
      .then(r => setHistory(r.data))
      .catch(() => {})
  }, [lessonId, outlineId, pptId, exId, practiceId])

  const formData = (extra: Record<string, any>) => {
    const fd = new FormData()
    fd.append('subject', subject)
    fd.append('grade_level', gradeLevel)
    fd.append('region', region)
    fd.append('topic', topic)
    fd.append('content', content)
    if (lessonId) fd.append('lesson_id', lessonId)
    Object.entries(extra).forEach(([k, v]) => fd.append(k, String(v)))
    return fd
  }

  const generate = async (endpoint: string, extra: Record<string, any>, onSuccess: (d: any) => void) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post(`/api/v1/course-tools/${endpoint}`, formData(extra))
      onSuccess(res.data)
    } catch (e: any) {
      setError(e.response?.data?.detail || t('tools.gen_failed'))
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

  const downloadWithAuth = async (endpoint: string) => {
    try {
      const res = await api.get(`/api/v1/course-tools/${endpoint}`, { responseType: 'blob' })
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
            {/* Lesson info card */}
            {lessonId && (
              <div className="bg-white rounded-xl border p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                  <BookOpen className="w-4 h-4 text-brand-600" />
                  {t('tools.linked_lesson')}
                </div>
                <p className="text-xs text-gray-500 truncate">{lessonId}</p>
              </div>
            )}

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
                      setTab(h.tool_type as Tab)
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
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
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
                      {(exResult.exercises || []).map((ex: any) => (
                        <div key={ex.id} className="border rounded-lg p-3">
                          <div className="text-sm font-medium text-gray-800">{ex.id}. {ex.question}</div>
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
                      {(practiceResult.practices || []).map((p: any) => (
                        <div key={p.id} className="border rounded-lg p-3">
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
                            const res = await api.post(`/api/v1/course-tools/practice/${practiceId}/merge-ppt`, fd)
                            setPptId(res.data.id)
                            setError('')
                            alert(t('tools.merge_success'))
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
          </div>
        </div>
      </div>
    </div>
  )
}
