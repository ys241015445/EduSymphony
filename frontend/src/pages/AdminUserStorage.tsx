import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import Card from '../components/ui/Card'
import { api } from '../services/api'
import { useT } from '../i18n/translations'
import { toast } from '../components/ui/Toast'
import { Loader2, Folder, File } from 'lucide-react'

type StorageRow = {
  name: string
  size: number
  is_file: boolean
  is_dir: boolean
}

export default function AdminUserStorage() {
  const { userId = '' } = useParams<{ userId: string }>()
  const t = useT()
  const [rows, setRows] = useState<StorageRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!userId) {
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const res = await api.get<StorageRow[]>(
          `/api/v1/admin/users/${encodeURIComponent(userId)}/storage-files`,
        )
        if (!cancelled) setRows(res.data || [])
      } catch (e: any) {
        if (!cancelled) {
          setRows([])
          toast.error(e?.response?.data?.detail || t('admin.load_failed'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [userId, t])

  const fmtSize = (n: number) => {
    if (n < 1024) return `${n} B`
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
    return `${(n / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/admin/users" className="hover:text-brand-600">{t('admin.users_title')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('admin.user_storage_title')}</span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t('admin.user_storage_title')}</h1>
        <p className="text-sm text-gray-500 mb-6">
          {t('admin.user_storage_subtitle')}
          {userId ? (
            <span className="ml-2 font-mono text-xs text-gray-600">({userId})</span>
          ) : null}
        </p>

        <Card padding={false}>
          {loading ? (
            <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
              <span>{t('dashboard.loading')}</span>
            </div>
          ) : rows.length === 0 ? (
            <div className="py-16 text-center text-sm text-gray-400">{t('admin.storage_empty')}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600 border-b border-gray-100">
                  <tr>
                    <th className="text-left font-medium px-4 py-3">{t('admin.storage_col_name')}</th>
                    <th className="text-left font-medium px-4 py-3">{t('admin.storage_col_kind')}</th>
                    <th className="text-right font-medium px-4 py-3">{t('admin.storage_col_size')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((r) => (
                    <tr key={r.name} className="hover:bg-gray-50/80">
                      <td className="px-4 py-3 font-medium text-gray-900">
                        <span className="inline-flex items-center gap-2 min-w-0">
                          {r.is_dir ? (
                            <Folder className="w-4 h-4 text-amber-500 shrink-0" />
                          ) : (
                            <File className="w-4 h-4 text-gray-400 shrink-0" />
                          )}
                          <span className="truncate">{r.name}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {r.is_dir ? t('admin.storage_kind_dir') : t('admin.storage_kind_file')}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600 tabular-nums">
                        {r.is_file ? fmtSize(r.size) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>
    </div>
  )
}
