import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Loader2, CheckCircle2, Clock, AlertCircle, Hourglass, AlertTriangle, PartyPopper,
  Layers, Play, RotateCcw, Download, FileDown, Package, Zap, FileText, Files,
} from 'lucide-react'
import Button from '../ui/Button'
import Card from '../ui/Card'
import { api } from '../../services/api'
import { toast } from '../ui/Toast'

// ───────────────────────────────────────────────────────────────────
// Shared types
// ───────────────────────────────────────────────────────────────────
export interface SharedSeriesLite {
  id: string
  title: string
  status: string
  total_weeks: number
  lessons_per_week: number
  error_message?: string | null
}

export interface SharedSeriesLesson {
  id: string
  title: string
  status: string
  progress: number
  sequence_order: number
}

export interface GenStats {
  totalExpected: number
  completed: number
  processing: number
  queued: number
  failed: number
  pending: number
  percent: number
  allDone: boolean
  hasFailed: boolean
}

// ───────────────────────────────────────────────────────────────────
// useGenerationStats hook — 4 桶计数 + 加权进度
// ───────────────────────────────────────────────────────────────────
export function useGenerationStats(
  series: SharedSeriesLite | null,
  lessons: SharedSeriesLesson[],
): GenStats {
  return useMemo(() => {
    const totalExpected = series ? series.total_weeks * series.lessons_per_week : 0
    const completed = lessons.filter(l => l.status === 'completed').length
    const processing = lessons.filter(l => l.status === 'processing').length
    const queued = lessons.filter(l => l.status === 'queued').length
    const failed = lessons.filter(l => l.status === 'failed').length
    const pending = Math.max(0, totalExpected - lessons.length)
    const weighted = lessons.reduce((acc, l) => {
      if (l.status === 'completed') return acc + 1
      if (l.status === 'processing') return acc + (l.progress || 0) / 100
      return acc
    }, 0)
    const percent = totalExpected > 0 ? Math.min(100, Math.round((weighted / totalExpected) * 100)) : 0
    const allDone = totalExpected > 0 && completed === totalExpected
    return {
      totalExpected, completed, processing, queued, failed, pending,
      percent, allDone, hasFailed: failed > 0,
    }
  }, [series, lessons])
}

// ───────────────────────────────────────────────────────────────────
// StatChip
// ───────────────────────────────────────────────────────────────────
export function StatChip({
  icon: Icon, color, label, value, spin,
}: { icon: any; color: 'green' | 'blue' | 'amber' | 'red'; label: string; value: number; spin?: boolean }) {
  const map = {
    green: 'bg-green-50 text-green-700 border-green-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  } as const
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${map[color]}`}>
      <Icon className={`w-4 h-4 ${spin ? 'animate-spin' : ''}`} />
      <div className="flex-1 min-w-0">
        <div className="text-xs leading-tight truncate">{label}</div>
        <div className="text-base font-semibold leading-tight">{value}</div>
      </div>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// ScheduleStat
// ───────────────────────────────────────────────────────────────────
export function ScheduleStat({
  label, value, unit, highlight,
}: { label: string; value: number | string; unit?: string; highlight?: boolean }) {
  return (
    <div className={`rounded-lg p-3 border ${highlight ? 'bg-brand-50 border-brand-200' : 'bg-white border-gray-200'}`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${highlight ? 'text-brand-700' : 'text-gray-900'}`}>
        {value}
        {unit && <span className="text-xs font-normal text-gray-500 ml-1">{unit}</span>}
      </div>
    </div>
  )
}

// ───────────────────────────────────────────────────────────────────
// GenerationStatusCard — 状态机 banner + 4 桶 chip + 进度条 + 操作区
// ───────────────────────────────────────────────────────────────────
export function GenerationStatusCard({
  series, stats, enqueueing, retrying, hasLessons,
  onGenerateAll, onRetryFailed, onGoExport, t,
}: {
  series: SharedSeriesLite
  stats: GenStats
  enqueueing: boolean
  retrying: boolean
  hasLessons: boolean
  onGenerateAll: () => void
  onRetryFailed: () => void
  onGoExport: () => void
  t: (k: string) => string
}) {
  const seriesStatus = series.status
  const inProgress = stats.processing > 0 || stats.queued > 0 || (hasLessons && !stats.allDone)

  let banner: { tone: 'amber' | 'blue' | 'green' | 'red' | 'gray'; icon: any; text: string; sub?: string }
  if (seriesStatus === 'generating_syllabus') {
    banner = { tone: 'blue', icon: Loader2, text: t('series.generating_syllabus') }
  } else if (seriesStatus === 'error') {
    banner = {
      tone: 'red', icon: AlertTriangle,
      text: t('university.error_status_msg'),
      sub: series.error_message || undefined,
    }
  } else if (stats.allDone) {
    banner = { tone: 'green', icon: PartyPopper, text: t('university.celebrate_done') }
  } else if (inProgress) {
    banner = { tone: 'blue', icon: Loader2, text: t('university.in_progress_msg') }
  } else if (seriesStatus === 'syllabus_ready' || (seriesStatus === 'generating' && !hasLessons)) {
    banner = { tone: 'green', icon: CheckCircle2, text: t('university.syllabus_ready_msg') }
  } else if (seriesStatus === 'created') {
    banner = { tone: 'amber', icon: Clock, text: t('university.created_msg') }
  } else {
    banner = { tone: 'gray', icon: Layers, text: t('series.progress') }
  }

  const toneMap = {
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    blue: 'bg-blue-50 text-blue-800 border-blue-200',
    green: 'bg-green-50 text-green-800 border-green-200',
    red: 'bg-red-50 text-red-800 border-red-200',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
  } as const
  const Icon = banner.icon
  const showCta =
    (seriesStatus === 'syllabus_ready' || (seriesStatus === 'generating' && !hasLessons))

  return (
    <Card>
      <div className={`flex items-start gap-3 p-3 mb-4 rounded-lg border ${toneMap[banner.tone]}`}>
        <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${banner.tone === 'blue' ? 'animate-spin' : ''}`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium">{banner.text}</div>
          {banner.sub && <div className="text-xs mt-0.5 opacity-80">{banner.sub}</div>}
        </div>
      </div>

      <div className="mb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-sm font-medium text-gray-700">{t('series.progress')}</span>
          <span className="text-sm font-semibold text-brand-600">
            {stats.percent}% ({stats.completed}/{stats.totalExpected})
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-brand-400 to-brand-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${stats.percent}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        <StatChip icon={CheckCircle2} color="green" label={t('university.stat_completed')} value={stats.completed} />
        <StatChip icon={Loader2} color="blue" label={t('university.stat_processing')} value={stats.processing} spin={stats.processing > 0} />
        <StatChip icon={Hourglass} color="amber" label={t('university.stat_queued')} value={stats.queued + stats.pending} />
        <StatChip icon={AlertCircle} color="red" label={t('university.stat_failed')} value={stats.failed} />
      </div>

      <div className="flex flex-wrap gap-2">
        {showCta && (
          <Button onClick={onGenerateAll} disabled={enqueueing}>
            {enqueueing ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Play className="w-4 h-4 mr-1.5" />}
            {t('series.start_generate')}
          </Button>
        )}
        {stats.hasFailed && (
          <Button variant="secondary" onClick={onRetryFailed} disabled={retrying}>
            {retrying ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <RotateCcw className="w-4 h-4 mr-1.5" />}
            {t('university.retry_failed').replace('{n}', String(stats.failed))}
          </Button>
        )}
        {stats.allDone && (
          <Button variant="secondary" onClick={onGoExport}>
            <Download className="w-4 h-4 mr-1.5" />
            {t('university.go_to_export')}
          </Button>
        )}
        {seriesStatus === 'error' && (
          <Button variant="secondary" onClick={onGenerateAll} disabled={enqueueing}>
            {enqueueing ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <RotateCcw className="w-4 h-4 mr-1.5" />}
            {t('university.retry_syllabus')}
          </Button>
        )}
      </div>
    </Card>
  )
}

// ───────────────────────────────────────────────────────────────────
// MyDocsQuickAccessCard — 跳"我的文档"+"下载历史"
// ───────────────────────────────────────────────────────────────────
export function MyDocsQuickAccessCard({
  seriesId, completed, forUserId, t,
}: { seriesId: string; completed: number; forUserId?: string; t: (k: string) => string }) {
  const docsDisabled = completed === 0
  const docsQs = (() => {
    const p = new URLSearchParams({ series: seriesId })
    if (forUserId) p.set('for_user_id', forUserId)
    return `?${p.toString()}`
  })()
  const exportsQs = (() => {
    const p = new URLSearchParams({ tab: 'exports' })
    if (forUserId) p.set('for_user_id', forUserId)
    return `?${p.toString()}`
  })()
  return (
    <Card>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center shrink-0">
          <Files className="w-5 h-5 text-brand-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-gray-900 mb-0.5">
            {t('university.my_docs_quick_title')}
          </h2>
          <p className="text-sm text-gray-600 mb-3">
            {t('university.my_docs_quick_desc').replace('{n}', String(completed))}
          </p>
          <div className="flex flex-wrap gap-2">
            {docsDisabled ? (
              <button
                type="button"
                disabled
                title={t('university.my_docs_quick_disabled')}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-200 text-gray-500 text-sm cursor-not-allowed"
              >
                <FileText className="w-4 h-4" />
                {t('university.my_docs_quick_go_docs')}
              </button>
            ) : (
              <Link
                to={`/documents${docsQs}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700 transition-colors"
              >
                <FileText className="w-4 h-4" />
                {t('university.my_docs_quick_go_docs')}
              </Link>
            )}
            <Link
              to={`/documents${exportsQs}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 text-sm hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4" />
              {t('university.my_docs_quick_go_exports')}
            </Link>
          </div>
        </div>
      </div>
    </Card>
  )
}

// ───────────────────────────────────────────────────────────────────
// SyllabusPreviewCard
// ───────────────────────────────────────────────────────────────────
export interface SyllabusItem {
  week: number
  lesson_num: number
  title: string
  topic?: string
  content_outline?: string
}

export function SyllabusPreviewCard({
  semesterOverview, syllabus, lessons, onMore, t, limit = 5,
}: {
  semesterOverview?: string
  syllabus: SyllabusItem[]
  lessons: SharedSeriesLesson[]
  onMore: () => void
  t: (k: string) => string
  limit?: number
}) {
  if (!syllabus.length && !semesterOverview) return null
  const preview = syllabus.slice(0, limit)
  const statusOf = (idx: number) => lessons.find(l => l.sequence_order === idx + 1)?.status

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <Layers className="w-5 h-5 text-brand-600" />
          {t('university.syllabus_preview')}
        </h2>
        {syllabus.length > limit && (
          <button onClick={onMore} className="text-xs text-brand-600 hover:underline">
            {t('university.syllabus_more').replace('{n}', String(syllabus.length))} →
          </button>
        )}
      </div>
      {semesterOverview && (
        <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap mb-3">
          {semesterOverview}
        </p>
      )}
      {!!preview.length && (
        <div className="space-y-1.5">
          {preview.map((it, idx) => {
            const st = statusOf(idx)
            const dot =
              st === 'completed' ? 'bg-green-500' :
              st === 'processing' ? 'bg-blue-500 animate-pulse' :
              st === 'queued' ? 'bg-amber-500' :
              st === 'failed' ? 'bg-red-500' : 'bg-gray-300'
            return (
              <div key={idx} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50">
                <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                <span className="text-xs text-gray-400 w-16 shrink-0">
                  {t('series.week_lesson').replace('{w}', String(it.week)).replace('{l}', String(it.lesson_num))}
                </span>
                <span className="text-sm text-gray-800 truncate">{it.title}</span>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

// ───────────────────────────────────────────────────────────────────
// ExportTab — 异步主推 + 同步回退（两个 dashboard 共用）
// ───────────────────────────────────────────────────────────────────
export function ExportTab({
  seriesId, stats, navigate, forUserId, t,
}: {
  seriesId: string
  stats: GenStats
  navigate: (to: string) => void
  forUserId?: string
  t: (k: string) => string
}) {
  const [fmt, setFmt] = useState('docx')
  const [withEx, setWithEx] = useState(false)
  const [async_, setAsync_] = useState(true)
  const [loading, setLoading] = useState<'merged' | 'zip' | ''>('')
  const [err, setErr] = useState('')

  const exportQueryParams = {
    format: fmt,
    include_exercises: withEx,
    ...(forUserId ? { for_user_id: forUserId } : {}),
  }

  const downloadSync = async (kind: 'merged' | 'zip') => {
    setLoading(kind)
    setErr('')
    try {
      const url = `/api/v1/export/series/${seriesId}/export-${kind}`
      const res = await api.get(url, { responseType: 'blob', params: exportQueryParams })
      const blob = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const match = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = match ? decodeURIComponent(match[1].replace(/"/g, '')) :
        kind === 'zip' ? `series-${seriesId}.zip` : `series-${seriesId}.${fmt}`
      const a = document.createElement('a')
      a.href = blob
      a.download = fname
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blob)
    } catch (e: any) {
      setErr(e.response?.data?.detail || t('university.export_failed'))
    } finally {
      setLoading('')
    }
  }

  const exportAsync = async (kind: 'merged' | 'zip') => {
    setLoading(kind)
    setErr('')
    try {
      const url = `/api/v1/export/series/${seriesId}/export-${kind}-async`
      await api.post(url, null, { params: exportQueryParams })
      toast.success(t('university.export_enqueued'))
      const p = new URLSearchParams({ tab: 'exports' })
      if (forUserId) p.set('for_user_id', forUserId)
      navigate(`/documents?${p.toString()}`)
    } catch (e: any) {
      const msg = e.response?.data?.detail || t('university.export_failed')
      setErr(msg)
      toast.error(msg)
    } finally {
      setLoading('')
    }
  }

  const trigger = (kind: 'merged' | 'zip') => async_ ? exportAsync(kind) : downloadSync(kind)

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="font-semibold text-gray-900 mb-3">{t('university.export_title')}</h2>
        <p className="text-xs text-gray-500 mb-3">{t('university.export_hint')}</p>

        {!stats.allDone && stats.completed === 0 && (
          <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
            {t('university.export_warn_empty')}
          </div>
        )}

        {err && <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">{err}</div>}

        <div className="grid grid-cols-2 gap-4 mb-3">
          <div>
            <label className="block text-sm text-gray-700 mb-1">{t('university.export_format')}</label>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm">
              <option value="docx">DOCX</option>
              <option value="pdf">PDF</option>
              <option value="md">Markdown</option>
              <option value="txt">TXT</option>
              <option value="json">JSON</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 mt-6">
            <input type="checkbox" checked={withEx} onChange={(e) => setWithEx(e.target.checked)} />
            {t('university.export_include_exercises')}
          </label>
        </div>

        <label className="flex items-start gap-2 text-sm text-gray-700 mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg cursor-pointer">
          <input type="checkbox" checked={async_} onChange={(e) => setAsync_(e.target.checked)} className="mt-0.5" />
          <div className="flex-1">
            <div className="font-medium flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-blue-500" />
              {t('university.export_async_label')}
            </div>
            <div className="text-xs text-gray-600 mt-0.5">{t('university.export_async_hint')}</div>
          </div>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => trigger('merged')} disabled={loading === 'merged'}
            className="p-4 rounded-xl border-2 border-gray-200 hover:border-brand-400 hover:bg-brand-50 transition-all text-left disabled:opacity-50">
            <div className="flex items-center gap-2 mb-1">
              {loading === 'merged' ? <Loader2 className="w-4 h-4 animate-spin text-brand-600" /> : <FileDown className="w-4 h-4 text-brand-600" />}
              <span className="font-medium text-gray-900">{t('university.export_merged')}</span>
            </div>
            <p className="text-xs text-gray-500">{t('university.export_merged_desc')}</p>
          </button>
          <button onClick={() => trigger('zip')} disabled={loading === 'zip'}
            className="p-4 rounded-xl border-2 border-gray-200 hover:border-brand-400 hover:bg-brand-50 transition-all text-left disabled:opacity-50">
            <div className="flex items-center gap-2 mb-1">
              {loading === 'zip' ? <Loader2 className="w-4 h-4 animate-spin text-brand-600" /> : <Package className="w-4 h-4 text-brand-600" />}
              <span className="font-medium text-gray-900">{t('university.export_zip')}</span>
            </div>
            <p className="text-xs text-gray-500">{t('university.export_zip_desc')}</p>
          </button>
        </div>

        {async_ && (
          <button
            onClick={() => {
              const p = new URLSearchParams({ tab: 'exports' })
              if (forUserId) p.set('for_user_id', forUserId)
              navigate(`/documents?${p.toString()}`)
            }}
            className="mt-3 text-xs text-brand-600 hover:underline flex items-center gap-1"
          >
            <Download className="w-3.5 h-3.5" />
            {t('university.go_to_downloads')} →
          </button>
        )}
      </Card>
    </div>
  )
}
