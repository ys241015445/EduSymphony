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
import {
  FileText,
  Download,
  Trash2,
  Loader2,
  Edit3,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Hourglass,
  History,
  FilePlus,
  Files,
  Folder,
  Sparkles,
  X,
} from 'lucide-react'

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
  const docScope = forUserId ? { for_user_id: forUserId } : undefined
  const userId = useAuthStore((s) => s.user?.id)

  const {
    library, loadingLib, fetchLibrary, ensureVersion,
    exports, loadingExports, fetchExports, deleteExport,
  } = useDocumentsStore()

  useEffect(() => {
    const libParams: { series_id?: string; for_user_id?: string } = {
      ...(seriesFilter ? { series_id: seriesFilter } : {}),
      ...(forUserId ? { for_user_id: forUserId } : {}),
    }
    fetchLibrary(Object.keys(libParams).length ? libParams : undefined)
    fetchExports(docScope)
  }, [fetchLibrary, fetchExports, seriesFilter, forUserId])

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
        fetchLibrary(Object.keys(libParams).length ? libParams : undefined)
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
      fetchExports(docScope)
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
  }, [userId, fetchExports, t, forUserId])

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
            <button
              type="button"
              onClick={clearScopeFilter}
              className="inline-flex items-center gap-1 text-amber-800 hover:text-amber-950 font-medium"
            >
              <X className="w-4 h-4" />
              {t('admin.clear_scope')}
            </button>
          </div>
        ) : null}

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('doc.library_title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('doc.library_subtitle')}</p>
          </div>
          <Button variant="ghost" onClick={() => { fetchLibrary(seriesFilter ? { series_id: seriesFilter } : undefined); fetchExports() }}>
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
  items, loading, onOpen, t,
}: {
  items: DocumentSummary[]
  loading: boolean
  onOpen: (it: DocumentSummary) => void
  t: (k: string) => string
}) {
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
        const cardKey = isVirtual ? `virtual-${it.lesson_plan_id}-${it.source_kind}` : (it.latest_version_id || `${it.lesson_plan_id}-${it.source_kind}`)
        return (
          <Card key={cardKey} padding={false} className="group hover:shadow-md hover:border-brand-200 transition-all cursor-pointer relative">
            <div className="p-4" onClick={() => onOpen(it)}>
              <div className="flex items-start justify-between mb-3">
                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                  isVirtual
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-blue-50 text-blue-600 border-blue-200'
                }`}>
                  <Folder className="w-3.5 h-3.5" />
                  {t(labelKey)}
                </div>
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
              <h3 className="font-semibold text-gray-900 truncate mb-1">{it.title}</h3>
              <p className="text-xs text-gray-400 mb-3">
                {it.updated_at ? new Date(it.updated_at).toLocaleString() : ''}
              </p>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-xs text-brand-600 group-hover:underline">
                  <Edit3 className="w-3.5 h-3.5" />
                  {isVirtual ? t('doc.virtual_open') : t('doc.open_editor')}
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
  const grouped = useMemo(() => {
    const queued = items.filter((i) => i.status === 'queued' || i.status === 'running')
    const ready = items.filter((i) => (i.status === 'done' || !i.status) && i.is_available)
    const expired = items.filter((i) => i.status === 'expired' || (i.file_path && !i.is_available))
    const failed = items.filter((i) => i.status === 'failed')
    return { queued, ready, expired, failed }
  }, [items])

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
      {grouped.expired.length > 0 && (
        <Section title={t('doc.exports_expired')} icon={Clock} color="text-gray-500">
          {grouped.expired.map((it) => (
            <ExportRow key={it.id} item={it} onDelete={onDelete} t={t} />
          ))}
        </Section>
      )}
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

function ExportRow({
  item, onDelete, t,
}: {
  item: ExportRecordItem
  onDelete: (id: string) => void
  t: (k: string) => string
}) {
  const isQueued = item.status === 'queued' || item.status === 'running'
  const isReady = (item.status === 'done' || !item.status) && item.is_available
  const isFailed = item.status === 'failed'
  const isExpired = item.status === 'expired' || (item.file_path && !item.is_available)

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
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('doc.download_failed'))
    }
  }

  const sizeKB = item.file_size ? Math.round(item.file_size / 1024) : null

  return (
    <div className="flex items-center gap-3 p-4">
      <FileText className="w-5 h-5 text-brand-500 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 truncate">{item.file_name}</span>
          <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
            {item.format}
          </span>
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
        {isReady && item.file_path && (
          <Button size="sm" variant="ghost" onClick={handleDownload}>
            <Download className="w-3.5 h-3.5 mr-1" />
            {t('doc.redownload')}
          </Button>
        )}
        {isExpired && (
          <span className="text-xs text-gray-400">{t('doc.expired')}</span>
        )}
        <button
          onClick={() => onDelete(item.id)}
          className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
          title={t('doc.delete')}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
