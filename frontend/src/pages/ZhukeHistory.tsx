import { useCallback, useEffect, useState } from 'react'

import { Link, useNavigate } from 'react-router-dom'

import Header from '../components/layout/Header'

import Button from '../components/ui/Button'

import Card from '../components/ui/Card'

import { useT } from '../i18n/translations'

import { toast } from '../components/ui/Toast'

import { api, ZHUKE_API_TIMEOUT_MS, ZHUKE_LIST_TIMEOUT_MS } from '../services/api'

import { useAuthStore } from '../stores/authStore'

import { hasCapability } from '../lib/access'

import { readApiErrorDetail } from '../lib/blobError'

import LockedComingSoon from '../components/semester/LockedComingSoon'

import {

  clearZhukeRecoverSession,

  postZhukeCancel,

  postZhukeRecover,

  postZhukeRegenerate,

  useZhukeHistoryPoll,

  zhukeIsActiveRecover,

  zhukeHasActiveJobs,

  handleZhuke409,

  isZhuke409,

} from '../hooks/useZhukeRecover'

import {

  ArrowLeft,

  Download,

  FileText,

  GraduationCap,

  Loader2,

  Square,

  Trash2,

  History,

  Sparkles,

  CheckCircle2,

  AlertTriangle,

  Hourglass,

  RotateCcw,

  Play,

} from 'lucide-react'



type HistoryItem = {

  result_id: string

  record_id: string

  course_name: string

  file_name: string

  lessons_count: number

  failures_count: number

  lessons_done?: number

  status: 'queued' | 'running' | 'done' | 'failed' | string

  file_size: number

  created_at: string

  file_exists?: boolean

  recovering?: boolean

  recover_action?: string | null

}



export default function ZhukeHistory() {

  const t = useT()

  const navigate = useNavigate()

  const user = useAuthStore((s) => s.user)

  const allowed = hasCapability(user as any, 'can_semester_helper')



  const [initialLoading, setInitialLoading] = useState(true)

  const [refreshing, setRefreshing] = useState(false)

  const [items, setItems] = useState<HistoryItem[]>([])

  const [downloadingId, setDownloadingId] = useState<string>('')

  const [deletingId, setDeletingId] = useState<string>('')

  const [stoppingId, setStoppingId] = useState<string>('')

  const [rebuildingId, setRebuildingId] = useState<string>('')

  const [regeneratingId, setRegeneratingId] = useState<string>('')

  const [retryingId, setRetryingId] = useState<string>('')



  const reload = useCallback(async (opts?: { silent?: boolean }) => {

    const silent = opts?.silent ?? false

    if (silent) setRefreshing(true)

    else setInitialLoading(true)

    try {

      const res = await api.get<HistoryItem[]>(

        '/api/v1/semester-helper/zhuke/history?limit=200',

        { timeout: ZHUKE_LIST_TIMEOUT_MS },

      )

      setItems(Array.isArray(res.data) ? res.data : [])

    } catch (e: unknown) {

      if (!silent) {

        toast.error(await readApiErrorDetail(e, 'Failed to load history'))

      }

    } finally {

      if (silent) setRefreshing(false)

      else setInitialLoading(false)

    }

  }, [])



  useEffect(() => {

    if (!allowed) return

    void reload()

  }, [allowed, reload])



  useZhukeHistoryPoll(items, reload)



  if (!allowed) {

    return <LockedComingSoon moduleTitle={t('zhuke.history_page_title')} />

  }



  const doDownload = async (rid: string, fmt: 'docx' | 'pdf', filename: string) => {

    if (!rid) {

      toast.error(t('zhuke.download_failed') || 'Download failed')

      return

    }

    const key = `${rid}:${fmt}`

    setDownloadingId(key)

    try {

      const res = await api.get(

        `/api/v1/semester-helper/zhuke/${encodeURIComponent(rid)}/download`,

        { params: { format: fmt }, responseType: 'blob' },

      )

      const url = URL.createObjectURL(res.data)

      const a = document.createElement('a')

      a.href = url

      a.download = fmt === 'pdf' ? filename.replace(/\.docx$/i, '.pdf') : filename

      document.body.appendChild(a)

      a.click()

      document.body.removeChild(a)

      URL.revokeObjectURL(url)

    } catch (e: unknown) {

      const status = (e as { response?: { status?: number } })?.response?.status

      if (status === 409) {

        // File missing on disk — surface, but DON'T auto-recover.

        // User must explicitly hit "Rebuild" or "Regenerate".

        toast.error(t('zhuke.file_missing_hint'))

      } else {

        toast.error(await readApiErrorDetail(e, t('zhuke.download_failed')))

      }

    } finally {

      setDownloadingId('')

    }

  }



  const doDelete = async (recordId: string) => {

    if (!recordId) return

    if (!window.confirm(t('zhuke.delete_confirm'))) return

    setDeletingId(recordId)

    try {

      await api.delete(`/api/v1/documents/exports/${encodeURIComponent(recordId)}`)

      setItems((prev) => prev.filter((x) => x.record_id !== recordId))

      toast.success(t('zhuke.delete_success'))

    } catch (e: unknown) {

      toast.error(await readApiErrorDetail(e, t('zhuke.delete_failed')))

    } finally {

      setDeletingId('')

    }

  }



  const doStop = async (resultId: string) => {

    if (!resultId) return

    if (!window.confirm(t('zhuke.stop_confirm'))) return

    setStoppingId(resultId)

    try {

      const res = await postZhukeCancel(resultId)

      clearZhukeRecoverSession(resultId)

      toast.success(res.message || t('zhuke.stop_success'))

      await reload({ silent: true })

    } catch (e: unknown) {

      toast.error(await handleZhuke409(e, t, 'zhuke.stop_failed'))

    } finally {

      setStoppingId('')

    }

  }



  const doRebuild = async (resultId: string) => {

    if (!resultId) return

    setRebuildingId(resultId)

    try {

      const res = await postZhukeRecover(resultId, { mode: 'rebuild' })

      if (res.action === 'impossible') {

        toast.error(t('zhuke.need_reupload'))

      } else if (res.file_exists && !res.recovering) {

        toast.success(res.message || t('zhuke.rebuild_from_cache'))

      } else {

        toast.info(res.message || t('zhuke.auto_recovering'))

      }

      await reload({ silent: true })

    } catch (e: unknown) {

      toast.error(await readApiErrorDetail(e, t('zhuke.recover_impossible')))

    } finally {

      setRebuildingId('')

    }

  }



  const doRegenerate = async (resultId: string) => {

    if (!resultId) return

    if (!window.confirm(t('zhuke.regenerate_confirm'))) return

    setRegeneratingId(resultId)

    try {

      const res = await postZhukeRegenerate(resultId)

      if (res.action === 'impossible') {

        toast.error(t('zhuke.need_reupload'))

      } else if (res.recovering || res.status === 'queued' || res.status === 'running') {

        toast.success(res.message || t('zhuke.regenerate_started'))

      } else if (res.file_exists) {

        toast.success(res.message || t('zhuke.generate_ok'))

      } else {

        toast.info(res.message || t('zhuke.auto_recovering'))

      }

      await reload({ silent: true })

    } catch (e: unknown) {

      toast.error(await handleZhuke409(e, t, 'zhuke.recover_impossible'))

    } finally {

      setRegeneratingId('')

    }

  }



  const doRetryFailed = async (resultId: string, failuresCount: number) => {

    if (!resultId || failuresCount <= 0) return

    if (!window.confirm(t('zhuke.retry_failed_confirm'))) return

    setRetryingId(resultId)

    try {

      const res = await postZhukeRegenerate(resultId)

      if (res.action === 'impossible') {

        toast.error(t('zhuke.need_reupload'))

      } else {

        toast.success(res.message || t('zhuke.regenerate_started'))

      }

      await reload({ silent: true })

    } catch (e: unknown) {

      toast.error(await handleZhuke409(e, t, 'zhuke.recover_impossible'))

    } finally {

      setRetryingId('')

    }

  }



  return (

    <div className="min-h-screen bg-gray-50">

      <Header />

      <main className="max-w-5xl mx-auto px-6 py-8">

        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">

          <Link to="/dashboard" className="hover:text-brand-600 inline-flex items-center gap-1">

            <ArrowLeft className="w-3.5 h-3.5" />

            {t('zhuke.back_dashboard')}

          </Link>

          <span>/</span>

          <Link to="/semester-helper" className="hover:text-brand-600">

            {t('semester_helper.title')}

          </Link>

          <span>/</span>

          <Link to="/semester-helper/zhuke" className="hover:text-brand-600">

            {t('zhuke.title')}

          </Link>

          <span>/</span>

          <span className="text-gray-900 font-medium">{t('zhuke.history_page_title')}</span>

        </div>



        <div className="flex items-start justify-between gap-3 mb-6 flex-wrap">

          <div className="flex items-center gap-3">

            <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center shrink-0">

              <History className="w-5 h-5 text-brand-600" />

            </div>

            <div>

              <h1 className="text-2xl font-bold text-gray-900">

                {t('zhuke.history_page_title')}

              </h1>

              <p className="text-sm text-gray-500 mt-0.5">

                {t('zhuke.history_page_subtitle')}

              </p>

            </div>

          </div>

          <div className="flex items-center gap-2">

            {refreshing && (

              <span className="text-xs text-gray-500 inline-flex items-center gap-1">

                <Loader2 className="w-3 h-3 animate-spin" />

                {t('zhuke.refreshing')}

              </span>

            )}

            <Button

              size="sm"

              variant="ghost"

              onClick={() => void reload()}

              disabled={initialLoading}

            >

              {initialLoading ? (

                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

              ) : (

                <Loader2 className="w-3.5 h-3.5 mr-1" />

              )}

              {t('doc.refresh')}

            </Button>

            <Button size="sm" onClick={() => navigate('/semester-helper/zhuke')}>

              <GraduationCap className="w-3.5 h-3.5 mr-1" />

              {t('zhuke.history_back_to_generate')}

            </Button>

          </div>

        </div>



        {initialLoading && items.length === 0 ? (

          <div className="py-20 text-center">

            <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" />

          </div>

        ) : items.length === 0 ? (

          <Card className="py-16 text-center text-sm text-gray-400">

            <FileText className="w-10 h-10 mx-auto text-gray-300 mb-3" />

            <div className="mb-3 text-gray-500">{t('zhuke.history_empty')}</div>

            <Link

              to="/semester-helper/zhuke"

              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-xs hover:bg-brand-700"

            >

              <Sparkles className="w-3.5 h-3.5" />

              {t('zhuke.history_empty_cta')}

            </Link>

          </Card>

        ) : (

          <Card padding={false}>

            <ul className="divide-y divide-gray-100">

              {items.map((h) => (

                <HistoryRow

                  key={h.record_id}

                  item={h}

                  downloadingKey={downloadingId}

                  deleting={deletingId === h.record_id}

                  stopping={stoppingId === h.result_id}

                  rebuilding={rebuildingId === h.result_id}

                  regenerating={regeneratingId === h.result_id}

                  retrying={retryingId === h.result_id}

                  onDownload={doDownload}

                  onDelete={doDelete}

                  onStop={doStop}

                  onRebuild={doRebuild}

                  onRegenerate={doRegenerate}

                  onRetryFailed={doRetryFailed}

                  t={t}

                />

              ))}

            </ul>

          </Card>

        )}

      </main>

    </div>

  )

}



function HistoryRow({

  item,

  downloadingKey,

  deleting,

  stopping,

  rebuilding,

  regenerating,

  retrying,

  onDownload,

  onDelete,

  onStop,

  onRebuild,

  onRegenerate,

  onRetryFailed,

  t,

}: {

  item: HistoryItem

  downloadingKey: string

  deleting: boolean

  stopping: boolean

  rebuilding: boolean

  regenerating: boolean

  retrying: boolean

  onDownload: (rid: string, fmt: 'docx' | 'pdf', filename: string) => void

  onDelete: (recordId: string) => void

  onStop: (resultId: string) => void

  onRebuild: (resultId: string) => void

  onRegenerate: (resultId: string) => void

  onRetryFailed: (resultId: string, failuresCount: number) => void

  t: (k: string) => string

}) {

  const activeRecover = zhukeIsActiveRecover(item)

  const isCancelled =

    item.recover_action === 'cancelled' || item.status === 'cancelled'

  const isGenerating =

    !isCancelled && (item.status === 'queued' || item.status === 'running')

  const hasActiveJobs = !isCancelled && zhukeHasActiveJobs(item)

  const fileMissing =

    !activeRecover &&

    !isGenerating &&

    !isCancelled &&

    (item.file_exists === false ||

      item.recover_action === 'impossible' ||

      (item.status === 'failed' && item.file_exists !== true))

  const isPartial =

    item.file_exists !== false &&

    item.status === 'done' &&

    typeof item.lessons_done === 'number' &&

    item.lessons_count > 0 &&

    item.lessons_done < item.lessons_count



  const statusLabel = isCancelled

    ? t('zhuke.cancelled_by_user')

    : isGenerating

    ? item.status === 'running'

      ? t('zhuke.progress_running')

          .replace('{done}', String(item.lessons_done ?? 0))

          .replace('{total}', String(item.lessons_count))

      : t('zhuke.status_queued')

    : activeRecover

    ? item.recover_action === 'relayout_queued'

      ? t('zhuke.layout_fixing')

      : t('zhuke.recovering_file')

    : fileMissing && item.recover_action === 'impossible'

    ? t('zhuke.need_reupload')

    : fileMissing

    ? t('doc.file_missing_badge')

    : isPartial

    ? t('zhuke.partial_file')

        .replace('{done}', String(item.lessons_done))

        .replace('{total}', String(item.lessons_count))

    : item.status === 'queued'

    ? t('zhuke.status_queued')

    : item.status === 'running'

    ? t('zhuke.status_running')

    : item.status === 'done'

    ? t('zhuke.status_done')

    : item.status === 'failed'

    ? t('zhuke.status_failed')

    : item.status



  const StatusIcon = isCancelled

    ? Square

    : isGenerating || activeRecover

    ? Loader2

    : fileMissing

    ? AlertTriangle

    : item.status === 'done'

    ? CheckCircle2

    : item.status === 'failed'

    ? AlertTriangle

    : item.status === 'running'

    ? Loader2

    : Hourglass



  const statusColor = isCancelled

    ? 'text-gray-500'

    : isGenerating || activeRecover

    ? 'text-amber-600'

    : fileMissing

    ? 'text-red-600'

    : isPartial

    ? 'text-amber-600'

    : item.status === 'done'

    ? 'text-green-600'

    : item.status === 'failed'

    ? 'text-red-600'

    : item.status === 'running'

    ? 'text-blue-600'

    : 'text-amber-600'



  const sizeKB = item.file_size ? Math.round(item.file_size / 1024) : null

  const isDone = item.status === 'done' && !!item.result_id && item.file_exists !== false

  const canStop = !!item.result_id && hasActiveJobs && item.recover_action !== 'impossible'

  const canRebuild =

    !!item.result_id &&

    fileMissing &&

    item.recover_action !== 'impossible' &&

    !hasActiveJobs

  const canRegenerate =

    !!item.result_id &&

    !hasActiveJobs &&

    item.recover_action !== 'impossible' &&

    (fileMissing || isPartial || item.status === 'failed' || isCancelled)

  const canRetryFailed =

    !!item.result_id &&

    item.failures_count > 0 &&

    !hasActiveJobs &&

    item.recover_action !== 'impossible'

  const dlDocxKey = `${item.result_id}:docx`

  const dlPdfKey = `${item.result_id}:pdf`



  return (

    <li className="p-4 flex items-start gap-3 hover:bg-gray-50/60">

      <FileText className="w-5 h-5 text-brand-500 shrink-0 mt-0.5" />

      <div className="flex-1 min-w-0">

        <div className="flex items-center gap-2 flex-wrap">

          <span className="font-medium text-gray-900 truncate">

            {item.course_name || item.file_name || '未命名'}

          </span>

          <span

            className={`inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded ${statusColor} bg-gray-50 border border-gray-100`}

          >

            <StatusIcon

              className={`w-3 h-3 ${(isGenerating || activeRecover) && !isCancelled ? 'animate-spin' : ''}`}

            />

            {statusLabel}

          </span>

          {item.failures_count > 0 && (

            <span className="text-[11px] text-amber-600">

              {t('zhuke.progress_failures').replace('{f}', String(item.failures_count))}

            </span>

          )}

        </div>

        <div className="text-xs text-gray-500 mt-1 truncate" title={item.file_name}>

          {item.file_name}

        </div>

        <div className="text-xs text-gray-400 mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">

          <span>

            {item.lessons_count} {t('zhuke.lessons_unit')}

          </span>

          {sizeKB ? <span>{sizeKB} KB</span> : null}

          {item.created_at ? <span>{new Date(item.created_at).toLocaleString()}</span> : null}

        </div>

      </div>

      <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">

        {isDone && (

          <>

            <Button

              size="sm"

              variant="ghost"

              onClick={() => onDownload(item.result_id, 'docx', item.file_name)}

              disabled={!!downloadingKey}

            >

              {downloadingKey === dlDocxKey ? (

                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

              ) : (

                <Download className="w-3.5 h-3.5 mr-1" />

              )}

              docx

            </Button>

            <Button

              size="sm"

              variant="ghost"

              onClick={() => onDownload(item.result_id, 'pdf', item.file_name)}

              disabled={!!downloadingKey}

            >

              {downloadingKey === dlPdfKey ? (

                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

              ) : (

                <FileText className="w-3.5 h-3.5 mr-1" />

              )}

              pdf

            </Button>

          </>

        )}

        {canRebuild && (

          <Button

            size="sm"

            variant="ghost"

            onClick={() => onRebuild(item.result_id)}

            disabled={rebuilding}

            className="text-brand-700 hover:text-brand-800 hover:bg-brand-50"

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

            onClick={() => onRegenerate(item.result_id)}

            disabled={regenerating}

            className="text-brand-700 hover:text-brand-800 hover:bg-brand-50"

          >

            {regenerating ? (

              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

            ) : (

              <Play className="w-3.5 h-3.5 mr-1" />

            )}

            {t('zhuke.regenerate')}

          </Button>

        )}

        {canRetryFailed && (

          <Button

            size="sm"

            variant="ghost"

            onClick={() => onRetryFailed(item.result_id, item.failures_count)}

            disabled={retrying}

            className="text-amber-700 hover:text-amber-800 hover:bg-amber-50"

          >

            {retrying ? (

              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

            ) : (

              <AlertTriangle className="w-3.5 h-3.5 mr-1" />

            )}

            {t('zhuke.retry_failed').replace('{n}', String(item.failures_count))}

          </Button>

        )}

        {fileMissing && item.recover_action === 'impossible' && (

          <Link

            to="/semester-helper/zhuke"

            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-brand-200 text-xs text-brand-700 hover:bg-brand-50"

          >

            <Sparkles className="w-3 h-3" />

            {t('doc.regenerate')}

          </Link>

        )}

        {canStop && (

          <Button

            size="sm"

            variant="ghost"

            onClick={() => onStop(item.result_id)}

            disabled={stopping}

            className="text-amber-700 hover:text-amber-800 hover:bg-amber-50"

          >

            {stopping ? (

              <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />

            ) : (

              <Square className="w-3.5 h-3.5 mr-1" />

            )}

            {t('zhuke.stop_regenerate')}

          </Button>

        )}

        <button

          onClick={() => onDelete(item.record_id)}

          disabled={deleting}

          className="p-1.5 text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"

          title={t('doc.delete')}

        >

          {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}

        </button>

      </div>

    </li>

  )

}


