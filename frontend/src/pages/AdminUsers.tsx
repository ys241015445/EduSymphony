import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import { toast } from '../components/ui/Toast'
import { Loader2, Files, Wrench, FolderOpen, FileEdit, LayoutGrid } from 'lucide-react'
import { parseAccessLevel } from '../lib/access'

type AdminUserRow = {
  id: string
  username: string
  email: string
  role: string
  access_level: string
  quota_remaining: number
}

function accessLabelKey(level: string): string {
  const v = parseAccessLevel(level)
  if (v === 'admin') return 'admin.access_admin'
  if (v === 'limited') return 'admin.access_limited'
  return 'admin.access_full'
}

export default function AdminUsers() {
  const t = useT()
  const [rows, setRows] = useState<AdminUserRow[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get<AdminUserRow[]>('/api/v1/admin/users')
      setRows(res.data)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('admin.load_failed'))
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600">{t('tools.dashboard')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('admin.users_title')}</span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-1">{t('admin.users_title')}</h1>
        <p className="text-sm text-gray-500 mb-6">{t('admin.users_subtitle')}</p>

        <Card padding={false}>
          {loading ? (
            <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
              <span>{t('dashboard.loading')}</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600 border-b border-gray-100">
                  <tr>
                    <th className="text-left font-medium px-4 py-3">{t('admin.col_username')}</th>
                    <th className="text-left font-medium px-4 py-3">{t('admin.col_email')}</th>
                    <th className="text-left font-medium px-4 py-3">{t('admin.col_role')}</th>
                    <th className="text-left font-medium px-4 py-3">{t('admin.col_access')}</th>
                    <th className="text-right font-medium px-4 py-3">{t('admin.col_quota')}</th>
                    <th className="text-right font-medium px-4 py-3 min-w-[280px]"> </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((u) => (
                    <tr key={u.id} className="hover:bg-gray-50/80">
                      <td className="px-4 py-3 font-medium text-gray-900">{u.username}</td>
                      <td className="px-4 py-3 text-gray-600 truncate max-w-[200px]" title={u.email}>
                        {u.email}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{u.role}</td>
                      <td className="px-4 py-3 text-gray-700">{t(accessLabelKey(u.access_level))}</td>
                      <td className="px-4 py-3 text-right text-gray-600 tabular-nums">{u.quota_remaining}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          <Link to={`/dashboard?for_user_id=${encodeURIComponent(u.id)}`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <LayoutGrid className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_workbench')}
                            </Button>
                          </Link>
                          <Link to={`/documents?for_user_id=${encodeURIComponent(u.id)}`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <Files className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_docs')}
                            </Button>
                          </Link>
                          <Link to={`/course-tools/library?for_user_id=${encodeURIComponent(u.id)}`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <Wrench className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_course_tools')}
                            </Button>
                          </Link>
                          <Link to={`/template-fill?for_user_id=${encodeURIComponent(u.id)}`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <FileEdit className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_template_fill')}
                            </Button>
                          </Link>
                          <Link to={`/admin/users/${encodeURIComponent(u.id)}/storage`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <FolderOpen className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_user_storage')}
                            </Button>
                          </Link>
                        </div>
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
