import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { toast } from '../components/ui/Toast'
import { useDocumentsStore, ExportRecordItem, DocumentSummary } from '../stores/documentsStore'
import { api } from '../services/api'
import { getSocket, joinUser } from '../services/socket'
import { useAuthStore } from '../stores/authStore'
import { parseAccessLevel, isAdmin } from '../lib/access'
import { humanizeSourceKind } from '../lib/exportKinds'
import { readApiErrorDetail } from '../lib/blobError'
import { clearZhukeRecoverSession, postZhukeCancel, postZhukeRecover, postZhukeRegenerate, fetchZhukeStatus } from '../hooks/useZhukeRecover'
import {
  FileText,
  Download,
  Trash2,
  Loader2,
  Edit3,
  Clock,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Hourglass,
  History,
  FilePlus,
  Files,
  Folder,
  Sparkles,
  X,
  ArrowLeft,
  GraduationCap,
  Layers,
  RotateCcw,
  Square,
  Play,
} from 'lucide-react'

type SeriesEmptyInfo = {
  seriesId: string
  forUserId?: string
  title?: string
  education_level?: string
  total: number
  completed: number
  processing: number
  queued: number
  failed: number
}

type Tab = 'docs' | 'exports'

const SOURCE_LABEL: Record<string, string> = {
  lesson_optimized: 'doc.source_optimized',
  lesson_draft: 'doc.source_draft',
  lesson: 'doc.source_lesson',
  bundle: 'doc.source_bundle',
  course_tool: 'doc.source_tool',
}

export default function DocumentsLibrary() {
  const t = useT()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = (searchParams.get('tab') as Tab) === 'exports' ? 'exports' : 'docs'
  const [tab, setTab] = useState<Tab>(initialTab)
  const seriesFilter = searchParams.get('series') || ''
  const forUserId = searchParams.get('for_user_id') || ''
  const includeDeletedQs = searchParams.get('include_deleted') === '1'
  const userId = useAuthStore((s) => s.user?.id)
  const userAccess = useAuthStore((s) => s.user?.access_level)
  const adminMode = isAdmin(parseAccessLevel(userAccess)) && !!forUserId
  const includeDeleted = adminMode && includeDeletedQs
  const docScope = forUserId
    ? { for_user_id: forUserId, include_deleted: includeDeleted || undefined }
    : undefined

  // 用 selector 单独订阅原子字段，避免每次 store set 都全量重渲染
  const library = useDocumentsStore((s) => s.library)
  const loadingLib = useDocumentsStore((s) => s.loadingLib)
  const exports = useDocumentsStore((s) => s.exports)
  const loadingExports = useDocumentsStore((s) => s.loadingExports)
  // action 直接从 store 取（不订阅），引用始终稳定，可放在 useEffect 外或不入 deps
  const ensureVersion = useDocumentsStore((s) => s.ensureVersion)
  const deleteExport = useDocumentsStore((s) => s.deleteExport)

  // 系列模式下，列表为空时的诊断信息
  const [seriesEmptyInfo, setSeriesEmptyInfo] = useState<SeriesEmptyInfo | null>(null)

  // 主拉取：仅依赖 URL 上真正影响请求的 primitive。
  // 用 getState() 取最新的 fetchLibrary / fetchExports，避免把 zustand action 放进 deps。
  useEffect(() => {
    const libParams: { series_id?: string; for_user_id?: string; include_deleted?: boolean } = {
      ...(seriesFilter ? { series_id: seriesFilter } : {}),
      ...(forUserId ? { for_user_id: forUserId } : {}),
      ...(includeDeleted ? { include_deleted: true } : {}),
    }
    const scope = forUserId ? { for_user_id: forUserId, include_deleted: includeDeleted || undefined } : undefined
    useDocumentsStore.getState().fetchLibrary(Object.keys(libParams).length ? libParams : undefined)
    useDocumentsStore.getState().fetchExports(scope)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesFilter, forUserId, includeDeleted])

  // 系列空态诊断：只在请求结束（loadingLib false）且列表为 0 时跑一次
  useEffect(() => {
    if (!seriesFilter) {
      setSeriesEmptyInfo(null)
      return
    }
    if (loadingLib) return
    if (library.length > 0) {
      setSeriesEmptyInfo(null)
      return
    }
    let cancelled = false
    const params = forUserId ? { for_user_id: forUserId } : undefined
    Promise.all([
      api.get(`/api/v1/series/${seriesFilter}`, { params }),
      api.get(`/api/v1/series/${seriesFilter}/lessons`, { params }),
    ])
      .then(([sr, lr]) => {
        if (cancelled) return
        const series = sr.data || {}
        const lessons: Array<{ status: string }> = Array.isArray(lr.data) ? lr.data : []
        const total = Number(series.total_weeks || 0) * Number(series.lessons_per_week || 0)
        const completed = lessons.filter((l) => l.status === 'completed').length
        const processing = lessons.filter((l) => l.status === 'processing').length
        const queued = lessons.filter((l) => l.status === 'queued').length
        const failed = lessons.filter((l) => l.status === 'failed').length
        setSeriesEmptyInfo({
          seriesId: seriesFilter,
          forUserId: forUserId || undefined,
          title: series.title,
          education_level: series.education_level,
          total: Math.max(total, lessons.length),
          completed, processing, queued, failed,
        })
      })
      .catch(() => {
        if (cancelled) return
        setSeriesEmptyInfo({
          seriesId: seriesFilter, forUserId: forUserId || undefined,
          total: 0, completed: 0, processing: 0, queued: 0, failed: 0,
        })
      })
    return () => { cancelled = true }
  }, [seriesFilter, forUserId, loadingLib, library.length])

  // 同步 URL ?tab= 到内部 state（在同一组件实例内切换时也生效）
  useEffect(() => {
    const next = searchParams.get('tab') === 'exports' ? 'exports' : 'docs'
    setTab(next)
  }, [searchParams])

  const clearSeriesFilter = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('series')
    setSearchParams(params, { replace: true })
  }

  const clearScopeFilter = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('for_user_id')
    params.delete('include_deleted')
    setSearchParams(params, { replace: true })
  }

  const toggleIncludeDeleted = (next: boolean) => {
    const params = new URLSearchParams(searchParams)
    if (next) params.set('include_deleted', '1')
    else params.delete('include_deleted')
    setSearchParams(params, { replace: true })
  }

  const handleOpenDoc = async (it: DocumentSummary) => {
    const q = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
    if (it.is_virtual) {
      if (!it.lesson_plan_id) {
        toast.error(t('doc.virtual_open_failed'))
        return
      }
      try {
        const res = await ensureVersion(it.lesson_plan_id, it.source_kind, docScope)
        navigate(`/documents/version/${res.version_id}${q}`)
        const libParams: { series_id?: string; for_user_id?: string } = {
          ...(seriesFilter ? { series_id: seriesFilter } : {}),
          ...(forUserId ? { for_user_id: forUserId } : {}),
        }
        useDocumentsStore.getState().fetchLibrary(Object.keys(libParams).length ? libParams : undefined)
      } catch (e: any) {
        toast.error(e?.response?.data?.detail || t('doc.virtual_open_failed'))
      }
    } else {
      navigate(`/documents/version/${it.latest_version_id}${q}`)
    }
  }

  // socket：异步导出状态变化时，局部更新单条 ExportRecord
  useEffect(() => {
    if (userId) joinUser(userId)
    const socket = getSocket()
    const onUpdate = (payload: any) => {
      if (!payload?.record_id) return
      // 直接拉一遍最新列表，最稳；列表小所以代价可接受
      const scope = forUserId ? { for_user_id: forUserId, include_deleted: includeDeleted || undefined } : undefined
      useDocumentsStore.getState().fetchExports(scope)
      if (payload.status === 'done') {
        toast.success(t('doc.export_done_toast'))
      } else if (payload.status === 'failed') {
        toast.error(t('doc.export_failed_toast'))
      }
    }
    socket.on('export_record_update', onUpdate)
    return () => {
      socket.off('export_record_update', onUpdate)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, forUserId, includeDeleted])

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600">{t('tools.dashboard')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('doc.library_title')}</span>
        </div>

        {forUserId ? (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-950">
            <span>{t('admin.docs_scope_hint').replace('{id}', forUserId)}</span>
            <div className="flex items-center gap-3">
              {adminMode && (
                <label className="inline-flex items-center gap-1.5 text-amber-900">
                  <input
                    type="checkbox"
                    checked={includeDeleted}
                    onChange={(e) => toggleIncludeDeleted(e.target.checked)}
                  />
                  <span>{t('admin.include_deleted')}</span>
                </label>
              )}
              <button
                type="button"
                onClick={clearScopeFilter}
                className="inline-flex items-center gap-1 text-amber-800 hover:text-amber-950 font-medium"
              >
                <X className="w-4 h-4" />
                {t('admin.clear_scope')}
              </button>
            </div>
          </div>
        ) : null}

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('doc.library_title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('doc.library_subtitle')}</p>
          </div>
          <Button variant="ghost" onClick={() => {
            const s = useDocumentsStore.getState()
            s.fetchLibrary(seriesFilter ? { series_id: seriesFilter } : undefined)
            s.fetchExports(forUserId ? { for_user_id: forUserId, include_deleted: includeDeleted || undefined } : undefined)
          }}>
            <Loader2 className="w-4 h-4 mr-1.5" />
            {t('doc.refresh')}
          </Button>
        </div>

        {seriesFilter && (
          <div className="mb-4 flex items-center justify-between gap-3 px-3 py-2 bg-brand-50 border border-brand-200 rounded-lg text-sm">
            <span className="text-brand-700">
              {t('doc.filter_series_active')}
            </span>
            <button
              onClick={clearSeriesFilter}
              className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-800"
            >
              <X className="w-3.5 h-3.5" />
              {t('doc.filter_clear')}
            </button>
          </div>
        )}

        <div className="flex gap-1.5 bg-white rounded-xl border p-1.5 mb-5 w-fit">
          <button
            onClick={() => setTab('docs')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === 'docs' ? 'bg-brand-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <Files className="w-4 h-4" />
            {t('doc.tab_docs')}
            <span className={`text-[11px] px-1.5 rounded-full ${tab === 'docs' ? 'bg-white/20' : 'bg-gray-100'}`}>
              {library.length}
            </span>
          </button>
          <button
            onClick={() => setTab('exports')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === 'exports' ? 'bg-brand-600 text-white shadow-sm' : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <History className="w-4 h-4" />
            {t('doc.tab_exports')}
            <span className={`text-[11px] px-1.5 rounded-full ${tab === 'exports' ? 'bg-white/20' : 'bg-gray-100'}`}>
              {exports.length}
            </span>
          </button>
        </div>

        {tab === 'docs' ? (
          <DocsTab
            items={library}
            loading={loadingLib}
            onOpen={handleOpenDoc}
            seriesEmptyInfo={seriesEmptyInfo}
            t={t}
          />
        ) : (
          <ExportsTab
            items={exports}
            loading={loadingExports}
            onDelete={async (id) => {
              if (!window.confirm(t('doc.confirm_delete_export'))) return
              try {
                await deleteExport(id)
                toast.success(t('doc.delete_success'))
              } catch (e: any) {
                toast.error(e?.response?.data?.detail || t('doc.delete_failed'))
              }
            }}
            t={t}
          />
        )}
      </main>
    </div>
  )
}

function DocsTab({
  items, loading, onOpen, seriesEmptyInfo, t,
}: {
  items: DocumentSummary[]
  loading: boolean
  onOpen: (it: DocumentSummary) => void
  seriesEmptyInfo: SeriesEmptyInfo | null
  t: (k: string) => string
}) {
  if (loading) {
    return (
      <div className="py-20 text-center">
        <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" />
      </div>
    )
  }
  if (!items.length && seriesEmptyInfo) {
    return <SeriesEmptyCard info={seriesEmptyInfo} t={t} />
  }
  if (!items.length) {
    return (
      <Card className="py-16 text-center text-sm text-gray-400">
        <FilePlus className="w-10 h-10 mx-auto text-gray-300 mb-3" />
        <div className="mb-2 text-gray-500">{t('doc.empty_title')}</div>
        <p className="text-xs text-gray-400 max-w-md mx-auto mb-4">{t('doc.empty_desc')}</p>
        <div className="flex items-center justify-center gap-2 flex-wrap">
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs hover:bg-brand-700"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {t('doc.empty_redirect_dashboard')}
          </Link>
          <Link
            to="/lesson/new"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 text-xs hover:bg-gray-50"
          >
            <FilePlus className="w-3.5 h-3.5" />
            {t('doc.empty_redirect_create')}
          </Link>
        </div>
      </Card>
    )
  }
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((it) => {
        const labelKey = SOURCE_LABEL[it.source_kind] || 'doc.source_other'
        const isVirtual = !!it.is_virtual
        const isDeleted = !!it.deleted_at
        const cardKey = isVirtual ? `virtual-${it.lesson_plan_id}-${it.source_kind}` : (it.latest_version_id || `${it.lesson_plan_id}-${it.source_kind}`)
        return (
          <Card
            key={cardKey}
            padding={false}
            className={`group transition-all relative ${
              isDeleted
                ? 'opacity-60 grayscale border-gray-200 cursor-default'
                : 'hover:shadow-md hover:border-brand-200 cursor-pointer'
            }`}
          >
            <div className="p-4" onClick={() => { if (!isDeleted) onOpen(it) }}>
              <div className="flex items-start justify-between mb-3">
                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                  isVirtual
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-blue-50 text-blue-600 border-blue-200'
                }`}>
                  <Folder className="w-3.5 h-3.5" />
                  {t(labelKey)}
                </div>
                <div className="flex items-center gap-1.5">
                  {isDeleted && (
                    <span
                      className="inline-flex items-center gap-1 text-[11px] text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full"
                      title={`${t('admin.deleted_at')} ${new Date(it.deleted_at!).toLocaleString()}`}
                    >
                      <Trash2 className="w-3 h-3" />
                      {t('admin.deleted_badge')}
                    </span>
                  )}
                  {isVirtual ? (
                    <span className="text-[11px] text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full font-medium">
                      {t('doc.virtual_badge')}
                    </span>
                  ) : (
                    <span className="text-[11px] text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                      v{it.latest_version_number} · {it.version_count} {t('doc.versions')}
                    </span>
                  )}
                </div>
              </div>
              <h3 className="font-semibold text-gray-900 truncate mb-1">{it.title}</h3>
              <p className="text-xs text-gray-400 mb-3">
                {it.updated_at ? new Date(it.updated_at).toLocaleString() : ''}
              </p>
              <div className="flex items-center gap-2">
                <span className={`flex items-center gap-1 text-xs ${isDeleted ? 'text-gray-400' : 'text-brand-600 group-hover:underline'}`}>
                  <Edit3 className="w-3.5 h-3.5" />
                  {isDeleted ? t('admin.deleted_view_only') : (isVirtual ? t('doc.virtual_open') : t('doc.open_editor'))}
                </span>
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}

function ExportsTab({
  items, loading, onDelete, t,
}: {
  items: ExportRecordItem[]
  loading: boolean
  onDelete: (id: string) => void
  t: (k: string) => string
}) {
  // Top-of-tab dropdown: filter by source_kind. Options are derived from the
  // actual data so we never show an empty bucket. Local-only (no URL state)
  // since the page already uses ?tab=exports / ?for_user_id and we don't want
  // to thrash the URL on every dropdown change.
  const [sourceKindFilter, setSourceKindFilter] = useState<string>('')

  const availableKinds = useMemo(() => {
    const set = new Set<string>()
    for (const it of items) if (it.source_kind) set.add(it.source_kind)
    return Array.from(set).sort()
  }, [items])

  const filteredItems = useMemo(() => {
    if (!sourceKindFilter) return items
    return items.filter((it) => it.source_kind === sourceKindFilter)
  }, [items, sourceKindFilter])

  const grouped = useMemo(() => {
    const queued = filteredItems.filter((i) => i.status === 'queued' || i.status === 'running')
    const ready = filteredItems.filter((i) => (i.status === 'done' || !i.status) && i.is_available)
    const failed = filteredItems.filter((i) => i.status === 'failed')
    // 「文件不可用」桶 = 真过期 OR (done/无状态 但磁盘没文件)。
    // 关键：queued/running/failed 行的 file_path 在 enqueue 时就写好但 worker
    // 还没把文件落盘 → 不能再误标为「过期」（旧分桶规则把这些都丢进了 expired
    // 桶，看起来就像「珠科教案明明在跑却被标已过期」）。
    const unavailable = filteredItems.filter((i) => {
      if (i.status === 'expired') return true
      if (i.file_path && !i.is_available && (i.status === 'done' || !i.status)) return true
      return false
    })
    return { queued, ready, failed, unavailable }
  }, [filteredItems])

  if (loading) {
    return (
      <div className="py-20 text-center">
        <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" />
      </div>
    )
  }
  if (!items.length) {
    return (
      <Card className="py-16 text-center text-sm text-gray-400">
        <Download className="w-10 h-10 mx-auto text-gray-300 mb-3" />
        <div className="mb-2">{t('doc.exports_empty')}</div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {availableKinds.length > 1 && (
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <span>{t('doc.filter_by_source_kind')}:</span>
          <select
            value={sourceKindFilter}
            onChange={(e) => setSourceKindFilter(e.target.value)}
            className="px-2 py-1 rounded border border-gray-300 text-xs bg-white"
          >
            <option value="">{t('doc.filter_all_sources')}</option>
            {availableKinds.map((k) => (
              <option key={k} value={k}>
                {humanizeSourceKind(k)}
              </option>
            ))}
          </select>
          {sourceKindFilter && filteredItems.length === 0 && (
            <span className="text-gray-400">— {t('doc.exports_empty')}</span>
          )}
        </div>
      )}

      <div className="space-y-6">
        {grouped.queued.length > 0 && (
          <Section title={t('doc.exports_queued')} icon={Hourglass} color="text-amber-600">
            {grouped.queued.map((it) => (
              <ExportRow key={it.id} item={it} onDelete={onDelete} t={t} />
            ))}
          </Section>
        )}
        {grouped.ready.length > 0 && (
          <Section title={t('doc.exports_ready')} icon={CheckCircle2} color="text-green-600">
            {grouped.ready.map((it) => (
              <ExportRow key={it.id} item={it} onDelete={onDelete} t={t} />
            ))}
          </Section>
        )}
        {grouped.failed.length > 0 && (
          <Section title={t('doc.exports_failed')} icon={AlertTriangle} color="text-red-600">
            {grouped.failed.map((it) => (
              <ExportRow key={it.id} item={it} onDelete={onDelete} t={t} />
            ))}
          </Section>
        )}
        {grouped.unavailable.length > 0 && (
          <Section title={t('doc.exports_unavailable')} icon={Clock} color="text-gray-500">
            {grouped.unavailable.map((it) => (
              <ExportRow key={it.id} item={it} onDelete={onDelete} t={t} />
            ))}
          </Section>
        )}
      </div>
    </div>
  )
}

function Section({
  title, icon: Icon, color, children,
}: {
  title: string
  icon: any
  color: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className={`flex items-center gap-2 mb-2 text-sm font-medium ${color}`}>
        <Icon className="w-4 h-4" />
        {title}
      </div>
      <div className="bg-white rounded-xl border divide-y">
        {children}
      </div>
    </div>
  )
}

function SeriesEmptyCard({ info, t }: { info: SeriesEmptyInfo; t: (k: string) => string }) {
  const { seriesId, forUserId, title, education_level, total, completed, processing, queued, failed } = info
  const isUni = education_level === 'university'
  const backTo = (() => {
    const base = isUni ? `/university/${seriesId}` : `/series/${seriesId}`
    if (forUserId) return `${base}?for_user_id=${encodeURIComponent(forUserId)}`
    return base
  })()
  const noLessons = total === 0 && processing === 0 && queued === 0 && failed === 0 && completed === 0
  const nothingDone = !noLessons && completed === 0

  return (
    <Card className="py-10 px-6">
      <div className="flex flex-col items-center text-center">
        <Files className="w-12 h-12 text-gray-300 mb-3" />
        <h3 className="text-base font-semibold text-gray-700 mb-1">
          {title || t('doc.empty_series_title')}
        </h3>
        <p className="text-xs text-gray-500 mb-4 max-w-md">
          {noLessons
            ? t('doc.empty_series_desc_nolessons')
            : nothingDone
              ? t('doc.empty_series_desc_pending')
              : t('doc.empty_series_desc_default')}
        </p>

        {!noLessons && (
          <div className="grid grid-cols-4 gap-2 mb-4 w-full max-w-md">
            <Stat icon={CheckCircle2} color="text-green-600 bg-green-50 border-green-200" v={completed} l={t('university.stat_completed')} />
            <Stat icon={Loader2} color="text-blue-600 bg-blue-50 border-blue-200" v={processing} l={t('university.stat_processing')} spin={processing > 0} />
            <Stat icon={Hourglass} color="text-amber-600 bg-amber-50 border-amber-200" v={queued} l={t('university.stat_queued')} />
            <Stat icon={AlertCircle} color="text-red-600 bg-red-50 border-red-200" v={failed} l={t('university.stat_failed')} />
          </div>
        )}

        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link
            to={backTo}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs hover:bg-brand-700"
          >
            {isUni ? <GraduationCap className="w-3.5 h-3.5" /> : <Layers className="w-3.5 h-3.5" />}
            {isUni ? t('doc.empty_series_back_uni') : t('doc.empty_series_back_series')}
          </Link>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 text-xs hover:bg-gray-50"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('doc.empty_redirect_dashboard')}
          </Link>
        </div>
      </div>
    </Card>
  )
}

function Stat({ icon: Icon, color, v, l, spin }: { icon: any; color: string; v: number; l: string; spin?: boolean }) {
  return (
    <div className={`flex flex-col items-center gap-0.5 rounded-lg border p-2 ${color}`}>
      <Icon className={`w-4 h-4 ${spin ? 'animate-spin' : ''}`} />
      <div className="text-base font-semibold leading-none">{v}</div>
      <div className="text-[10px] leading-tight">{l}</div>
    </div>
  )
}

function ExportRow({
  item, onDelete, t,
}: {
  item: ExportRecordItem
  onDelete: (id: string) => void
  t: (k: string) => string
}) {
  const isDeleted = !!item.deleted_at
  const isZhuke = item.source_kind === 'zhuke_generation'
  const zhukeRid = (item.params?.result_id as string | undefined) || item.job_id || ''
  const [zhukeLive, setZhukeLive] = useState<{ recovering?: boolean; status?: string; recover_action?: string | null } | null>(null)

  useEffect(() => {
    if (!isZhuke || !zhukeRid) {
      setZhukeLive(null)
      return
    }
    let cancelled = false
    void fetchZhukeStatus(zhukeRid, { light: true })
      .then((s) => {
        if (!cancelled) setZhukeLive({
          recovering: s.recovering,
          status: s.status,
          recover_action: s.recover_action ?? null,
        })
      })
      .catch(() => {
        if (!cancelled) setZhukeLive(null)
      })
    return () => {
      cancelled = true
    }
  }, [isZhuke, zhukeRid])

  const isCancelled = !!(zhukeLive && (zhukeLive.status === 'cancelled' || zhukeLive.recover_action === 'cancelled'))
  const isQueued = isZhuke && zhukeRid
    ? !isCancelled && !!(zhukeLive?.recovering || zhukeLive?.status === 'queued' || zhukeLive?.status === 'running')
    : item.status === 'queued' || item.status === 'running'
  const isReady = (item.status === 'done' || !item.status) && item.is_available && !isDeleted && !isQueued
  // 真过期 = backend 显式标 'expired'；旧的「file_path && !is_available」对珠科
  // 这种 expires_at=null + 长 TTL 的来源毫无意义，会把"docx 写失败/被清"误诊。
  const isExpired = item.status === 'expired'
  // 文件丢失 = DB 说 done（或无状态），file_path 写了但磁盘没文件。区别于过期
  // 是这种情况可以「重新生成」一次拿回来。
  const isFileMissing =
    !!item.file_path &&
    !item.is_available &&
    (item.status === 'done' || !item.status) &&
    !isDeleted &&
    !isCancelled
  const isFailed = isZhuke && zhukeLive
    ? zhukeLive.status === 'failed' && !zhukeLive.recovering
    : item.status === 'failed'

  const [rebuilding, setRebuilding] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [recoverImpossible, setRecoverImpossible] = useState(false)
  const [recoverBusy, setRecoverBusy] = useState(false)

  const canRegenerate =
    isZhuke &&
    !!zhukeRid &&
    !isQueued &&
    !recoverBusy &&
    !recoverImpossible &&
    (isFileMissing || isFailed || isCancelled)

  const handleRegenerate = async () => {
    if (!zhukeRid) return
    if (!window.confirm(t('zhuke.regenerate_confirm'))) return
    setRegenerating(true)
    setRecoverBusy(true)
    try {
      const res = await postZhukeRegenerate(zhukeRid)
      if (res.action === 'impossible') {
        setRecoverImpossible(true)
        toast.error(t('zhuke.need_reupload'))
      } else if (res.recovering || res.status === 'queued' || res.status === 'running') {
        toast.success(res.message || t('zhuke.regenerate_started'))
        window.location.reload()
      } else if (res.file_exists && !res.recovering) {
        toast.success(res.message || t('zhuke.generate_ok'))
        window.location.reload()
      } else {
        toast.info(res.message || t('zhuke.recovering_file'))
        window.location.reload()
      }
    } catch (e: unknown) {
      toast.error(await readApiErrorDetail(e, t('zhuke.recover_impossible')))
    } finally {
      setRegenerating(false)
      setRecoverBusy(false)
    }
  }

  const handleRebuild = async () => {
    if (!zhukeRid) return
    setRebuilding(true)
    setRecoverBusy(true)
    try {
      const res = await postZhukeRecover(zhukeRid, { mode: 'rebuild' })
      if (res.action === 'impossible') {
        setRecoverImpossible(true)
        toast.error(t('zhuke.need_reupload'))
      } else if (res.file_exists && !res.recovering) {
        toast.success(res.message || t('zhuke.rebuild_from_cache'))
        window.location.reload()
      } else {
        toast.info(res.message || t('zhuke.recovering_file'))
      }
    } catch (e: unknown) {
      toast.error(await readApiErrorDetail(e, t('zhuke.recover_impossible')))
    } finally {
      setRebuilding(false)
      setRecoverBusy(false)
    }
  }

  const handleStop = async () => {
    if (!zhukeRid) return
    if (!window.confirm(t('zhuke.stop_confirm'))) return
    setStopping(true)
    try {
      const res = await postZhukeCancel(zhukeRid)
      clearZhukeRecoverSession(zhukeRid)
      toast.success(res.message || t('zhuke.stop_success'))
      window.location.reload()
    } catch (e: unknown) {
      toast.error(await readApiErrorDetail(e, t('zhuke.stop_failed')))
    } finally {
      setStopping(false)
    }
  }

  const handleDownload = async () => {
    try {
      const res = await api.get(`/api/v1/documents/exports/${item.id}/download`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = item.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      toast.error(await readApiErrorDetail(e, t('doc.download_failed')))
    }
  }

  const handleZhukeDownload = async (fmt: 'docx' | 'pdf') => {
    if (!zhukeRid) {
      toast.error(t('doc.download_failed'))
      return
    }
    try {
      const res = await api.get(
        `/api/v1/semester-helper/zhuke/${encodeURIComponent(zhukeRid)}/download`,
        { params: { format: fmt }, responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = fmt === 'pdf' ? item.file_name.replace(/\.docx$/i, '.pdf') : item.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        // File missing on disk — DO NOT auto-recover (was triggering unwanted
        // regeneration after user stopped). Surface the situation and let the
        // explicit "Rebuild from cache" / "Regenerate" buttons do the work.
        toast.error(t('zhuke.file_missing_hint'))
      } else {
        toast.error(await readApiErrorDetail(e, t('doc.download_failed')))
      }
    }
  }

  const sizeKB = item.file_size ? Math.round(item.file_size / 1024) : null
  const sourceKindLabel = humanizeSourceKind(item.source_kind)

  return (
    <div className={`flex items-center gap-3 p-4 ${isDeleted ? 'opacity-60 grayscale' : ''}`}>
      <FileText className="w-5 h-5 text-brand-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-gray-900 truncate">{item.file_name}</span>
          {sourceKindLabel && (
            <span className="text-[10px] px-1.5 py-0.5 bg-brand-50 text-brand-700 border border-brand-100 rounded">
              {sourceKindLabel}
            </span>
          )}
          <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
            {item.format}
          </span>
          {isDeleted && (
            <span
              className="inline-flex items-center gap-1 text-[10px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded"
              title={`${t('admin.deleted_at')} ${new Date(item.deleted_at!).toLocaleString()}`}
            >
              <Trash2 className="w-3 h-3" />
              {t('admin.deleted_badge')}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
          {sizeKB ? ` · ${sizeKB} KB` : ''}
          {item.expires_at ? ` · ${t('doc.expires_at')} ${new Date(item.expires_at).toLocaleDateString()}` : ''}
        </div>
        {isFailed && item.error_message && (
          <p className="text-xs text-red-500 mt-1 line-clamp-1">{item.error_message}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {isQueued && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            {item.status === 'running' ? t('doc.status_running') : t('doc.status_queued')}
          </span>
        )}
        {isCancelled && (
          <span className="inline-flex items-center gap-1 text-xs text-gray-500">
            {t('zhuke.cancelled_by_user')}
          </span>
        )}
        {isReady && isZhuke && zhukeRid ? (
          <>
            <Button size="sm" variant="ghost" onClick={() => handleZhukeDownload('docx')}>
              <Download className="w-3.5 h-3.5 mr-1" />
              docx
            </Button>
            <Button size="sm" variant="ghost" onClick={() => handleZhukeDownload('pdf')}>
              <FileText className="w-3.5 h-3.5 mr-1" />
              pdf
            </Button>
          </>
        ) : isReady && item.file_path ? (
          <Button size="sm" variant="ghost" onClick={handleDownload}>
            <Download className="w-3.5 h-3.5 mr-1" />
            {t('doc.redownload')}
          </Button>
        ) : null}
        {isFileMissing && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600">
            {recoverBusy ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {isQueued
                  ? (zhukeLive?.status === 'running'
                      ? t('doc.status_running')
                      : t('doc.status_queued'))
                  : t('zhuke.recovering_file')}
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5" />
                {t('doc.file_missing_badge')}
              </>
            )}
          </span>
        )}
        {isFileMissing && isZhuke && !!zhukeRid && !recoverImpossible && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void handleRebuild()}
            disabled={rebuilding}
            className="text-brand-700"
          >
            {rebuilding ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
            ) : (
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
            )}
            {t('zhuke.rebuild_from_cache')}
          </Button>
        )}
        {canRegenerate && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void handleRegenerate()}
            disabled={regenerating}
            className="text-brand-700"
          >
            {regenerating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
            ) : (
              <Play className="w-3.5 h-3.5 mr-1" />
            )}
            {t('zhuke.regenerate')}
          </Button>
        )}
        {isZhuke && isQueued && !!zhukeRid && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void handleStop()}
            disabled={stopping}
            className="text-amber-700"
          >
            {stopping ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
            ) : (
              <Square className="w-3.5 h-3.5 mr-1" />
            )}
            {t('zhuke.stop_regenerate')}
          </Button>
        )}
        {isFileMissing && isZhuke && recoverImpossible && (
          <Link
            to="/semester-helper/zhuke"
            className="text-xs text-brand-600 hover:text-brand-700 hover:underline"
          >
            {t('doc.regenerate')}
          </Link>
        )}
        {isExpired && !isFileMissing && (
          <span className="text-xs text-gray-400">{t('doc.expired')}</span>
        )}
        {!isDeleted && (
          <button
            onClick={() => onDelete(item.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
            title={t('doc.delete')}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
