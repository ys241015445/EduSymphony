import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../services/api'
import { useT } from '../../i18n/translations'
import {
  BookOpen, Layers, FileText, Presentation, ClipboardList, Dumbbell,
  X, Search, ChevronRight, ChevronDown, Check, Link2,
} from 'lucide-react'

export type ToolKind = 'outline' | 'ppt' | 'exercises' | 'practice'

export type SourceRef =
  | { kind: 'lesson'; id: string; title: string; mode: 'auto' | 'optimized' | 'draft' | 'original' }
  | { kind: 'series'; id: string; title: string }
  | { kind: ToolKind; id: string; title: string }

interface Props {
  value: SourceRef | null
  onChange: (v: SourceRef | null) => void
  presetSeriesId?: string
  className?: string
}

interface LessonRow {
  id: string
  title: string
  subject?: string
  grade_level?: string
  status?: string
  sequence_order?: number
}

interface SeriesRow {
  id: string
  title: string
  subject?: string
  grade_level?: string
  status?: string
}

interface ToolRow {
  id: string
  title: string
  tool_type: string
  params?: Record<string, any>
  created_at: string
}

const MODES: { v: 'auto' | 'optimized' | 'draft' | 'original'; k: string }[] = [
  { v: 'auto', k: 'tools.source_mode_auto' },
  { v: 'optimized', k: 'tools.source_mode_optimized' },
  { v: 'draft', k: 'tools.source_mode_draft' },
  { v: 'original', k: 'tools.source_mode_original' },
]

// Each tool group config
const TOOL_GROUPS: { kind: ToolKind; icon: any; labelKey: string }[] = [
  { kind: 'outline', icon: FileText, labelKey: 'tools.source_tab_outline' },
  { kind: 'ppt', icon: Presentation, labelKey: 'tools.source_tab_ppt' },
  { kind: 'exercises', icon: ClipboardList, labelKey: 'tools.source_tab_exercises' },
  { kind: 'practice', icon: Dumbbell, labelKey: 'tools.source_tab_practice' },
]

export default function SourcePicker({ value, onChange, presetSeriesId, className = '' }: Props) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')

  const [lessons, setLessons] = useState<LessonRow[]>([])
  const [series, setSeries] = useState<SeriesRow[]>([])
  const [toolResults, setToolResults] = useState<ToolRow[]>([])
  const [seriesLessons, setSeriesLessons] = useState<Record<string, LessonRow[]>>({})
  const [expandedSeries, setExpandedSeries] = useState<string | null>(presetSeriesId || null)
  const [loaded, setLoaded] = useState(false)
  const [loading, setLoading] = useState(false)

  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // Load lessons + series + ALL course-tool history in parallel on first open
  useEffect(() => {
    if (!open || loaded) return
    setLoading(true)
    Promise.all([
      api.get('/api/v1/lessons', { params: { limit: 100 } })
        .then(r => setLessons(r.data || [])).catch(() => setLessons([])),
      api.get('/api/v1/series').then(r => setSeries(r.data || [])).catch(() => setSeries([])),
      // no tool_type filter → returns all types (outline/ppt/exercises/practice)
      api.get('/api/v1/course-tools/history')
        .then(r => setToolResults(r.data || [])).catch(() => setToolResults([])),
    ]).finally(() => {
      setLoading(false)
      setLoaded(true)
    })
  }, [open, loaded])

  const loadSeriesLessons = async (sid: string) => {
    if (seriesLessons[sid]) return
    try {
      const r = await api.get(`/api/v1/series/${sid}/lessons`)
      setSeriesLessons(prev => ({ ...prev, [sid]: r.data || [] }))
    } catch {
      setSeriesLessons(prev => ({ ...prev, [sid]: [] }))
    }
  }

  useEffect(() => {
    if (presetSeriesId && open) loadSeriesLessons(presetSeriesId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetSeriesId, open])

  const kw = keyword.trim().toLowerCase()
  const filteredLessons = useMemo(() => {
    if (!kw) return lessons
    return lessons.filter(l => (l.title || '').toLowerCase().includes(kw))
  }, [lessons, kw])

  const filteredSeries = useMemo(() => {
    if (!kw) return series
    return series.filter(s => (s.title || '').toLowerCase().includes(kw))
  }, [series, kw])

  // Split toolResults by type
  const toolsByKind = useMemo(() => {
    const map: Record<ToolKind, ToolRow[]> = { outline: [], ppt: [], exercises: [], practice: [] }
    for (const r of toolResults) {
      const k = r.tool_type as ToolKind
      if (k in map) map[k].push(r)
    }
    return map
  }, [toolResults])

  const filterTools = (list: ToolRow[]) => {
    if (!kw) return list
    return list.filter(r => {
      const title = r.title || r.params?.topic || r.params?.subject || ''
      return (title || '').toLowerCase().includes(kw)
    })
  }

  const pick = (v: SourceRef) => {
    onChange(v)
    setOpen(false)
    setKeyword('')
  }

  const clear = (e?: React.MouseEvent) => {
    e?.stopPropagation()
    onChange(null)
  }

  const setMode = (mode: 'auto' | 'optimized' | 'draft' | 'original') => {
    if (value && value.kind === 'lesson') {
      onChange({ ...value, mode })
    }
  }

  const kindLabel = (k: SourceRef['kind']): string => {
    const map: Record<string, string> = {
      lesson: 'tools.source_kind_lesson',
      series: 'tools.source_kind_series',
      outline: 'tools.source_kind_outline',
      ppt: 'tools.source_kind_ppt',
      exercises: 'tools.source_kind_exercises',
      practice: 'tools.source_kind_practice',
    }
    return t(map[k])
  }

  const triggerLabel = () => {
    if (!value) return t('tools.source_pick')
    return kindLabel(value.kind) + '：' + (value.title || t('tools.source_untitled'))
  }

  const triggerIcon = () => {
    if (!value) return <Link2 className="w-4 h-4 text-gray-400" />
    if (value.kind === 'lesson') return <BookOpen className="w-4 h-4 text-brand-600" />
    if (value.kind === 'series') return <Layers className="w-4 h-4 text-brand-600" />
    if (value.kind === 'ppt') return <Presentation className="w-4 h-4 text-brand-600" />
    if (value.kind === 'exercises') return <ClipboardList className="w-4 h-4 text-brand-600" />
    if (value.kind === 'practice') return <Dumbbell className="w-4 h-4 text-brand-600" />
    return <FileText className="w-4 h-4 text-brand-600" />
  }

  const rowTitle = (r: ToolRow) => r.title || r.params?.topic || r.params?.subject || t('tools.source_untitled')

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <label className="text-xs font-medium text-gray-600 mb-1 block">
        {t('tools.source_picker_title')}
      </label>

      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border bg-white text-sm text-left transition-colors ${
          open
            ? 'border-brand-500 ring-2 ring-brand-100'
            : value
              ? 'border-brand-200 hover:border-brand-400'
              : 'border-gray-200 hover:border-gray-300'
        }`}
      >
        {triggerIcon()}
        <span className={`flex-1 truncate ${value ? 'text-gray-800' : 'text-gray-400'}`} title={triggerLabel()}>
          {triggerLabel()}
        </span>
        {value && (
          <span
            role="button"
            onClick={clear}
            className="text-gray-400 hover:text-red-500 flex-shrink-0"
            title={t('tools.source_unlink')}
          >
            <X className="w-3.5 h-3.5" />
          </span>
        )}
        <ChevronDown className={`w-4 h-4 text-gray-400 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {value && value.kind === 'lesson' && (
        <div className="mt-1.5 flex items-center gap-1 flex-wrap">
          <span className="text-[11px] text-gray-400 mr-0.5">{t('tools.source_mode_label')}：</span>
          {MODES.map(m => (
            <button
              key={m.v}
              type="button"
              onClick={() => setMode(m.v)}
              className={`px-2 py-0.5 rounded-full text-[11px] border transition-all ${
                value.mode === m.v
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
              }`}
            >
              {t(m.k)}
            </button>
          ))}
        </div>
      )}

      {open && (
        <div className="absolute z-30 left-0 right-0 mt-1 bg-white rounded-xl border border-gray-200 shadow-xl overflow-hidden">
          <div className="p-2 border-b border-gray-100">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={keyword}
                onChange={e => setKeyword(e.target.value)}
                placeholder={t('tools.source_search_ph')}
                autoFocus
                className="w-full pl-8 pr-2 py-1.5 rounded-lg border border-gray-200 text-xs focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
              />
            </div>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading && (
              <p className="text-xs text-gray-400 py-6 text-center">{t('tools.source_loading')}</p>
            )}

            {!loading && (
              <>
                {/* Group: Lessons */}
                <div>
                  <div className="sticky top-0 z-10 flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border-b border-gray-100 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    <BookOpen className="w-3 h-3" />
                    {t('tools.source_tab_lesson')}
                    <span className="ml-auto text-gray-400 font-normal">{filteredLessons.length}</span>
                  </div>
                  {filteredLessons.length === 0 ? (
                    <p className="text-[11px] text-gray-400 py-2 text-center">{t('tools.source_empty_list')}</p>
                  ) : (
                    <div className="py-1">
                      {filteredLessons.map(l => {
                        const active = value?.kind === 'lesson' && value.id === l.id
                        return (
                          <button
                            key={l.id}
                            type="button"
                            onClick={() => pick({ kind: 'lesson', id: l.id, title: l.title, mode: 'auto' })}
                            className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 ${
                              active ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-700'
                            }`}
                          >
                            <BookOpen className="w-3 h-3 text-brand-600 flex-shrink-0" />
                            <span className="truncate flex-1">{l.title}</span>
                            {l.status && (
                              <span className={`text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 ${
                                l.status === 'completed' ? 'bg-green-100 text-green-600' :
                                l.status === 'failed' ? 'bg-red-100 text-red-600' :
                                'bg-gray-100 text-gray-500'
                              }`}>{l.status}</span>
                            )}
                            {active && <Check className="w-3 h-3 text-brand-600 flex-shrink-0" />}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Group: Series */}
                <div>
                  <div className="sticky top-0 z-10 flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border-b border-t border-gray-100 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                    <Layers className="w-3 h-3" />
                    {t('tools.source_tab_series')}
                    <span className="ml-auto text-gray-400 font-normal">{filteredSeries.length}</span>
                  </div>
                  {filteredSeries.length === 0 ? (
                    <p className="text-[11px] text-gray-400 py-2 text-center">{t('tools.source_empty_list')}</p>
                  ) : (
                    <div className="py-1">
                      {filteredSeries.map(s => {
                        const expanded = expandedSeries === s.id
                        const subs = seriesLessons[s.id] || []
                        const active = value?.kind === 'series' && value.id === s.id
                        return (
                          <div key={s.id}>
                            <div className="flex items-stretch">
                              <button
                                type="button"
                                onClick={() => pick({ kind: 'series', id: s.id, title: s.title })}
                                className={`flex-1 text-left px-3 py-1.5 text-xs flex items-center gap-2 ${
                                  active ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-700'
                                }`}
                                title={t('tools.source_syllabus_whole')}
                              >
                                <Layers className="w-3 h-3 text-brand-600 flex-shrink-0" />
                                <span className="truncate flex-1">{s.title}</span>
                                <span className="text-[10px] text-brand-600 flex-shrink-0">{t('tools.source_syllabus_whole')}</span>
                                {active && <Check className="w-3 h-3 text-brand-600 flex-shrink-0" />}
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  const next = expanded ? null : s.id
                                  setExpandedSeries(next)
                                  if (next) loadSeriesLessons(s.id)
                                }}
                                className="px-2 hover:bg-gray-100 border-l border-gray-100"
                                title={t('tools.source_syllabus_one_lesson')}
                              >
                                <ChevronRight className={`w-3 h-3 text-gray-400 transition-transform ${expanded ? 'rotate-90' : ''}`} />
                              </button>
                            </div>
                            {expanded && (
                              <div className="bg-gray-50/60 px-3 py-1 space-y-0.5 border-b border-gray-100">
                                {subs.length === 0 ? (
                                  <p className="text-[11px] text-gray-400 py-1.5 text-center">{t('tools.source_empty_list')}</p>
                                ) : (
                                  subs.map(sl => {
                                    const subActive = value?.kind === 'lesson' && value.id === sl.id
                                    return (
                                      <button
                                        key={sl.id}
                                        type="button"
                                        onClick={() => pick({ kind: 'lesson', id: sl.id, title: sl.title, mode: 'auto' })}
                                        className={`w-full text-left pl-6 pr-2 py-1 rounded text-[11px] flex items-center gap-2 ${
                                          subActive ? 'bg-brand-50 text-brand-700' : 'hover:bg-white text-gray-600'
                                        }`}
                                      >
                                        <span className="text-gray-400 flex-shrink-0">#{sl.sequence_order ?? ''}</span>
                                        <span className="truncate flex-1">{sl.title}</span>
                                        {sl.status === 'completed' && <Check className="w-3 h-3 text-green-500 flex-shrink-0" />}
                                      </button>
                                    )
                                  })
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Groups: 4 tool types */}
                {TOOL_GROUPS.map(g => {
                  const Icon = g.icon
                  const list = filterTools(toolsByKind[g.kind])
                  return (
                    <div key={g.kind}>
                      <div className="sticky top-0 z-10 flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 border-b border-t border-gray-100 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                        <Icon className="w-3 h-3" />
                        {t(g.labelKey)}
                        <span className="ml-auto text-gray-400 font-normal">{list.length}</span>
                      </div>
                      {list.length === 0 ? (
                        <p className="text-[11px] text-gray-400 py-2 text-center">{t('tools.source_empty_list')}</p>
                      ) : (
                        <div className="py-1">
                          {list.map(r => {
                            const active = value?.kind === g.kind && value.id === r.id
                            const title = rowTitle(r)
                            return (
                              <button
                                key={r.id}
                                type="button"
                                onClick={() => pick({ kind: g.kind, id: r.id, title })}
                                className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 ${
                                  active ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-700'
                                }`}
                              >
                                <Icon className="w-3 h-3 text-brand-600 flex-shrink-0" />
                                <span className="truncate flex-1">{title}</span>
                                <span className="text-[10px] text-gray-400 flex-shrink-0">{(r.created_at || '').slice(0, 10)}</span>
                                {active && <Check className="w-3 h-3 text-brand-600 flex-shrink-0" />}
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function applySourceToFormData(fd: FormData, src: SourceRef | null) {
  if (!src) return
  switch (src.kind) {
    case 'lesson':
      fd.append('lesson_id', src.id)
      fd.append('source_mode', src.mode || 'auto')
      break
    case 'series':
      fd.append('series_id', src.id)
      break
    case 'outline':
      fd.append('outline_id', src.id)
      break
    case 'ppt':
      fd.append('ppt_id', src.id)
      break
    case 'exercises':
      fd.append('exercises_id', src.id)
      break
    case 'practice':
      fd.append('practice_id', src.id)
      break
  }
}
