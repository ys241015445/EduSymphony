import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import Card from '../components/ui/Card'
import { api } from '../services/api'
import { useT } from '../i18n/translations'
import { toast } from '../components/ui/Toast'
import { Loader2, Download, FileText, AlertTriangle, Trash2 } from 'lucide-react'
import { humanizeSourceKind } from '../lib/exportKinds'

type ExportRow = {
  id: string
  created_at?: string | null
  updated_at?: string | null
  format: string
  source_kind: string
  file_name: string
  file_size?: number | null
  status: string
  lesson_plan_id?: string | null
  lesson_title?: string | null
  series_id?: string | null
  series_title?: string | null
  error_message?: string | null
  expires_at?: string | null
  deleted_at?: string | null
  has_file?: boolean
}

type Summary = {
  total: number
  last_30d: number
  by_format: Record<string, number>
  by_source_kind: Record<string, number>
  by_status: Record<string, number>
  top_documents: Array<{ lesson_plan_id?: string | null; lesson_title?: string | null; count: number }>
}

const fmtSize = (n?: number | null) => {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleString() : '—')

export default function AdminUserExports() {
  const { userId = '' } = useParams<{ userId: string }>()
  const t = useT()
  const [rows, setRows] = useState<ExportRow[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterFmt, setFilterFmt] = useState('')
  const [filterSrc, setFilterSrc] = useState('')
  const [includeDeleted, setIncludeDeleted] = useState(true)

  useEffect(() => {
    if (!userId) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const params: Record<string, any> = {
          limit: 500,
          include_deleted: includeDeleted,
        }
        if (filterFmt) params.format = filterFmt
        if (filterSrc) params.source_kind = filterSrc
        const [lr, sr] = await Promise.all([
          api.get<ExportRow[]>(
            `/api/v1/admin/users/${encodeURIComponent(userId)}/exports`,
            { params },
          ),
          api.get<Summary>(
            `/api/v1/admin/users/${encodeURIComponent(userId)}/exports/summary`,
            { params: { include_deleted: includeDeleted } },
          ),
        ])
        if (!cancelled) {
          setRows(lr.data || [])
          setSummary(sr.data || null)
        }
      } catch (e: any) {
        if (!cancelled) {
          setRows([])
          setSummary(null)
          toast.error(e?.response?.data?.detail || t('admin.load_failed'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [userId, t, filterFmt, filterSrc, includeDeleted])

  const formatOptions = useMemo(
    () => Object.keys(summary?.by_format || {}).sort(),
    [summary?.by_format],
  )
  const sourceOptions = useMemo(
    () => Object.keys(summary?.by_source_kind || {}).sort(),
    [summary?.by_source_kind],
  )

  const handleDownload = async (r: ExportRow) => {
    try {
      const res = await api.get(`/api/v1/documents/exports/${encodeURIComponent(r.id)}/download`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = r.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('admin.exports_action_no_file'))
    }
  }

  const handleDelete = async (r: ExportRow) => {
    if (!window.confirm(t('admin.exports_action_delete_confirm'))) return
    try {
      await api.delete(`/api/v1/documents/exports/${encodeURIComponent(r.id)}`)
      // 标记为软删，刷新当前行；列表会在下次包含已删除时仍出现
      setRows((prev) => prev.map((x) => (x.id === r.id ? { ...x, deleted_at: new Date().toISOString() } : x)))
      toast.success(t('admin.save_success'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('admin.save_failed'))
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/admin/users" className="hover:text-brand-600">{t('admin.users_title')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('admin.exports_title')}</span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t('admin.exports_title')}</h1>
        <p className="text-sm text-gray-500 mb-6">
          {t('admin.exports_subtitle')}
          {userId ? <span className="ml-2 font-mono text-xs text-gray-600">({userId})</span> : null}
        </p>

        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
            <span>{t('dashboard.loading')}</span>
          </div>
        ) : (
          <div className="space-y-6">
            {summary && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard label={t('admin.exports_total')} value={summary.total} icon={Download} />
                <StatCard label={t('admin.exports_last_30d')} value={summary.last_30d} icon={FileText} />
                <StatCard
                  label={t('admin.exports_top_format')}
                  value={topKey(summary.by_format)}
                  textValue
                />
                <StatCard
                  label={t('admin.exports_top_source')}
                  value={topKey(summary.by_source_kind)}
                  textValue
                />
              </div>
            )}

            {summary && (
              <Card>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <BreakdownPanel title={t('admin.exports_by_format')} m={summary.by_format} />
                  <BreakdownPanel title={t('admin.exports_by_source')} m={summary.by_source_kind} />
                  <BreakdownPanel title={t('admin.exports_by_status')} m={summary.by_status} />
                </div>
              </Card>
            )}

            {summary && summary.top_documents.length > 0 && (
              <Card>
                <h2 className="font-semibold text-gray-900 mb-3">{t('admin.exports_top_docs')}</h2>
                <ul className="divide-y divide-gray-100">
                  {summary.top_documents.map((it, i) => (
                    <li key={`${it.lesson_plan_id || ''}-${i}`} className="flex items-center justify-between py-2 text-sm">
                      <span className="truncate text-gray-800">{it.lesson_title || it.lesson_plan_id || '—'}</span>
                      <span className="font-mono text-gray-600">{it.count}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card padding={false}>
              <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-100">
                <label className="text-sm text-gray-600 flex items-center gap-1.5">
                  <span>{t('admin.exports_filter_format')}</span>
                  <select
                    value={filterFmt}
                    onChange={(e) => setFilterFmt(e.target.value)}
                    className="px-2 py-1 rounded border border-gray-200 text-sm"
                  >
                    <option value="">{t('admin.exports_all')}</option>
                    {formatOptions.map((k) => (
                      <option key={k} value={k}>{k}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm text-gray-600 flex items-center gap-1.5">
                  <span>{t('admin.exports_filter_source')}</span>
                  <select
                    value={filterSrc}
                    onChange={(e) => setFilterSrc(e.target.value)}
                    className="px-2 py-1 rounded border border-gray-200 text-sm"
                  >
                    <option value="">{t('admin.exports_all')}</option>
                    {sourceOptions.map((k) => (
                      <option key={k} value={k}>{k}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm text-gray-600 flex items-center gap-1.5 ml-auto">
                  <input
                    type="checkbox"
                    checked={includeDeleted}
                    onChange={(e) => setIncludeDeleted(e.target.checked)}
                  />
                  <span>{t('admin.exports_include_deleted')}</span>
                </label>
              </div>

              {rows.length === 0 ? (
                <div className="py-16 text-center text-sm text-gray-400">{t('admin.exports_empty')}</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600 border-b border-gray-100">
                      <tr>
                        <th className="text-left font-medium px-4 py-3">{t('admin.exports_col_created')}</th>
                        <th className="text-left font-medium px-4 py-3">{t('admin.exports_col_doc')}</th>
                        <th className="text-left font-medium px-4 py-3">{t('admin.exports_col_format')}</th>
                        <th className="text-left font-medium px-4 py-3">{t('admin.exports_col_source')}</th>
                        <th className="text-left font-medium px-4 py-3">{t('admin.exports_col_status')}</th>
                        <th className="text-right font-medium px-4 py-3">{t('admin.exports_col_size')}</th>
                        <th className="text-right font-medium px-4 py-3">{t('admin.exports_col_actions')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {rows.map((r) => {
                        const isDeleted = !!r.deleted_at
                        const canDownload = !isDeleted && r.status === 'done' && !!r.has_file
                        return (
                          <tr key={r.id} className={`hover:bg-gray-50/80 ${isDeleted ? 'opacity-60' : ''}`}>
                            <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{fmtDate(r.created_at)}</td>
                            <td className="px-4 py-3 text-gray-800">
                              <div
                                className="font-medium truncate max-w-[280px]"
                                title={r.file_name}
                              >
                                {r.lesson_title || r.file_name}
                              </div>
                              {r.series_title ? (
                                <div className="text-xs text-gray-500 truncate max-w-[280px]" title={r.series_title}>
                                  {r.series_title}
                                </div>
                              ) : null}
                              {!r.lesson_title && r.file_name ? (
                                <div className="text-[11px] text-gray-400 truncate max-w-[280px]" title={r.file_name}>
                                  {r.file_name}
                                </div>
                              ) : null}
                              {isDeleted && (
                                <span className="inline-flex items-center gap-1 text-[11px] mt-0.5 text-gray-400">
                                  <Trash2 className="w-3 h-3" />
                                  {t('admin.exports_deleted_badge')} {fmtDate(r.deleted_at)}
                                </span>
                              )}
                              {r.status === 'failed' && r.error_message ? (
                                <div className="text-xs text-red-500 line-clamp-1 mt-0.5">
                                  <AlertTriangle className="inline w-3 h-3 mr-0.5" />
                                  {r.error_message}
                                </div>
                              ) : null}
                            </td>
                            <td className="px-4 py-3 uppercase text-xs text-gray-600">{r.format}</td>
                            <td className="px-4 py-3 text-gray-600">{humanizeSourceKind(r.source_kind)}</td>
                            <td className="px-4 py-3 text-gray-600">{r.status}</td>
                            <td className="px-4 py-3 text-right text-gray-600 tabular-nums">{fmtSize(r.file_size)}</td>
                            <td className="px-4 py-3 text-right">
                              <div className="inline-flex items-center justify-end gap-1.5">
                                {canDownload ? (
                                  <button
                                    type="button"
                                    onClick={() => handleDownload(r)}
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-brand-200 text-brand-700 bg-brand-50 hover:bg-brand-100 text-xs"
                                    title={t('admin.exports_action_download')}
                                  >
                                    <Download className="w-3.5 h-3.5" />
                                  </button>
                                ) : !isDeleted ? (
                                  <button
                                    type="button"
                                    disabled
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-gray-200 text-gray-400 bg-gray-50 text-xs cursor-not-allowed"
                                    title={t('admin.exports_action_no_file')}
                                  >
                                    <Download className="w-3.5 h-3.5" />
                                  </button>
                                ) : null}
                                {!isDeleted && (
                                  <button
                                    type="button"
                                    onClick={() => handleDelete(r)}
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 text-xs"
                                    title={t('admin.exports_action_delete')}
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}
      </main>
    </div>
  )
}

function StatCard({ label, value, icon: Icon, textValue }: { label: string; value: any; icon?: any; textValue?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="text-xs text-gray-500 flex items-center gap-1.5">
        {Icon ? <Icon className="w-3.5 h-3.5" /> : null}
        {label}
      </div>
      <div className={`mt-1 font-semibold text-gray-900 ${textValue ? 'text-base truncate' : 'text-2xl tabular-nums'}`}>
        {value ?? '—'}
      </div>
    </div>
  )
}

function BreakdownPanel({ title, m }: { title: string; m: Record<string, number> }) {
  const entries = Object.entries(m).sort((a, b) => b[1] - a[1])
  if (entries.length === 0) {
    return (
      <div>
        <div className="text-xs text-gray-500 mb-1">{title}</div>
        <div className="text-xs text-gray-400">—</div>
      </div>
    )
  }
  return (
    <div>
      <div className="text-xs text-gray-500 mb-2">{title}</div>
      <ul className="space-y-1">
        {entries.map(([k, v]) => (
          <li key={k} className="flex items-center justify-between text-sm">
            <span className="text-gray-700 truncate">{k}</span>
            <span className="font-mono text-gray-600">{v}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function topKey(m: Record<string, number>): string {
  const entries = Object.entries(m).sort((a, b) => b[1] - a[1])
  return entries[0] ? `${entries[0][0]} (${entries[0][1]})` : '—'
}
