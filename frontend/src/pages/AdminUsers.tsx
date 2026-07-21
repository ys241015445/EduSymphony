import { useEffect, useMemo, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import { toast } from '../components/ui/Toast'
import { Loader2, Files, Wrench, FolderOpen, FileEdit, LayoutGrid, Download, Settings2, X } from 'lucide-react'
import { parseAccessLevel, CAPABILITY_FLAGS, CAPABILITY_DEFAULTS, type CapabilityFlag } from '../lib/access'

type AdminUserRow = {
  id: string
  username: string
  email: string
  role: string
  access_level: string
  quota_remaining: number
  can_course_tools?: boolean
  can_template_fill?: boolean
  can_university?: boolean
  can_series?: boolean
  can_next_lesson?: boolean
  can_export?: boolean
  can_semester_helper?: boolean
  export_credits?: number
  export_pay_exempt?: boolean
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
  const [editing, setEditing] = useState<AdminUserRow | null>(null)

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

  const onSaved = (next: AdminUserRow) => {
    setRows((prev) => prev.map((r) => (r.id === next.id ? next : r)))
    setEditing(null)
  }

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
                          <Button
                            size="sm"
                            variant="secondary"
                            className="!py-1.5 !border-brand-300 !text-brand-700 !bg-brand-50 hover:!bg-brand-100"
                            onClick={() => setEditing(u)}
                          >
                            <Settings2 className="w-3.5 h-3.5 mr-1" />
                            {t('admin.edit_permissions')}
                          </Button>
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
                          <Link to={`/admin/users/${encodeURIComponent(u.id)}/exports`}>
                            <Button size="sm" variant="secondary" className="!py-1.5">
                              <Download className="w-3.5 h-3.5 mr-1" />
                              {t('admin.open_exports')}
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
      {editing && (
        <PermissionsModal
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={onSaved}
          t={t}
        />
      )}
    </div>
  )
}

function PermissionsModal({
  user, onClose, onSaved, t,
}: {
  user: AdminUserRow
  onClose: () => void
  onSaved: (next: AdminUserRow) => void
  t: (k: string) => string
}) {
  const [level, setLevel] = useState<string>(parseAccessLevel(user.access_level))
  const [quota, setQuota] = useState<number>(user.quota_remaining ?? 0)
  const [payExempt, setPayExempt] = useState<boolean>(!!user.export_pay_exempt)
  const [credits, setCredits] = useState<number>(user.export_credits ?? 0)
  const [flags, setFlags] = useState<Record<CapabilityFlag, boolean>>(() => {
    const init = {} as Record<CapabilityFlag, boolean>
    for (const f of CAPABILITY_FLAGS) {
      const v = (user as any)[f]
      init[f] = v === undefined || v === null ? CAPABILITY_DEFAULTS[f] : !!v
    }
    return init
  })
  const [saving, setSaving] = useState(false)

  const dirty = useMemo(() => {
    if (level !== parseAccessLevel(user.access_level)) return true
    if (quota !== (user.quota_remaining ?? 0)) return true
    if (payExempt !== !!user.export_pay_exempt) return true
    if (credits !== (user.export_credits ?? 0)) return true
    return CAPABILITY_FLAGS.some((f) => {
      const orig = (user as any)[f]
      const origBool = orig === undefined || orig === null ? CAPABILITY_DEFAULTS[f] : !!orig
      return origBool !== flags[f]
    })
  }, [level, quota, payExempt, credits, flags, user])

  const handleSave = async () => {
    setSaving(true)
    try {
      const body: any = {}
      if (level !== parseAccessLevel(user.access_level)) body.access_level = level
      if (quota !== (user.quota_remaining ?? 0)) body.quota_remaining = quota
      if (payExempt !== !!user.export_pay_exempt) body.export_pay_exempt = payExempt
      if (credits !== (user.export_credits ?? 0)) body.export_credits = credits
      CAPABILITY_FLAGS.forEach((f) => {
        const raw = (user as any)[f]
        const orig = raw === undefined || raw === null ? CAPABILITY_DEFAULTS[f] : !!raw
        if (orig !== flags[f]) body[f] = flags[f]
      })
      const res = await api.patch<AdminUserRow>(`/api/v1/admin/users/${encodeURIComponent(user.id)}`, body)
      toast.success(t('admin.save_success'))
      onSaved(res.data)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('admin.save_failed'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{t('admin.edit_permissions')}</h2>
            <p className="text-xs text-gray-500 mt-0.5">{user.username} · {user.email}</p>
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <label className="block">
            <span className="block text-xs text-gray-500 mb-1">{t('admin.col_access')}</span>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
            >
              <option value="full">{t('admin.access_full')}</option>
              <option value="limited">{t('admin.access_limited')}</option>
              <option value="admin">{t('admin.access_admin')}</option>
            </select>
          </label>
          <label className="block">
            <span className="block text-xs text-gray-500 mb-1">{t('admin.col_quota')}</span>
            <input
              type="number"
              min={0}
              value={quota}
              onChange={(e) => setQuota(Math.max(0, Number(e.target.value) || 0))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
            />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <label className="block">
            <span className="block text-xs text-gray-500 mb-1">{t('admin.col_export_credits')}</span>
            <input
              type="number"
              min={0}
              value={credits}
              onChange={(e) => setCredits(Math.max(0, Number(e.target.value) || 0))}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
            />
          </label>
          <label className={`flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer text-sm mt-5 ${payExempt ? 'border-brand-300 bg-brand-50' : 'border-gray-200 bg-white'}`}>
            <input
              type="checkbox"
              checked={payExempt}
              onChange={(e) => setPayExempt(e.target.checked)}
            />
            <span className="text-gray-800">{t('admin.export_pay_exempt')}</span>
          </label>
        </div>

        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">{t('admin.capability_section')}</div>
          <div className="grid grid-cols-2 gap-2">
            {CAPABILITY_FLAGS.map((f) => (
              <label
                key={f}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer text-sm ${
                  flags[f] ? 'border-brand-300 bg-brand-50' : 'border-gray-200 bg-white'
                }`}
              >
                <input
                  type="checkbox"
                  checked={flags[f]}
                  onChange={(e) => setFlags((prev) => ({ ...prev, [f]: e.target.checked }))}
                />
                <span className="text-gray-800">{t(`admin.cap_${f}`)}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button size="sm" variant="secondary" onClick={onClose}>
            {t('admin.cancel')}
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!dirty || saving}>
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
            {t('admin.save')}
          </Button>
        </div>
      </div>
    </div>
  )
}
