import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { api } from '../services/api'
import { useT } from '../i18n/translations'
import { useJobsStore } from '../stores/jobsStore'
import { toast } from '../components/ui/Toast'
import {
  FileText,
  Presentation,
  ClipboardList,
  Dumbbell,
  Loader2,
  Download,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Eye,
  Layers,
  X,
} from 'lucide-react'

type ToolType = 'outline' | 'ppt' | 'exercises' | 'practice'
type Tab = 'all' | ToolType | 'pending'

interface LibItem {
  id: string
  tool_type: ToolType
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  error_message?: string | null
  has_file?: boolean
  created_at: string
  params?: Record<string, any>
}

const TOOL_META: Record<ToolType, { icon: typeof FileText; color: string; labelKey: string }> = {
  outline: { icon: FileText, color: 'text-blue-600 bg-blue-50 border-blue-200', labelKey: 'tools.tab_outline' },
  ppt: { icon: Presentation, color: 'text-purple-600 bg-purple-50 border-purple-200', labelKey: 'tools.tab_ppt' },
  exercises: { icon: ClipboardList, color: 'text-green-600 bg-green-50 border-green-200', labelKey: 'tools.tab_exercises' },
  practice: { icon: Dumbbell, color: 'text-orange-600 bg-orange-50 border-orange-200', labelKey: 'tools.tab_practice' },
}

export default function CourseToolsLibrary() {
  const t = useT()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const highlightId = searchParams.get('highlight') || ''
  const highlightTool = (searchParams.get('tool') || '') as ToolType | ''
  const forUserId = searchParams.get('for_user_id') || ''
  const scopeParams = forUserId ? { for_user_id: forUserId } : undefined
  const [items, setItems] = useState<LibItem[]>([])
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<Tab>(
    highlightTool && (['outline', 'ppt', 'exercises', 'practice'] as const).includes(highlightTool as any)
      ? (highlightTool as Tab)
      : 'all'
  )
  const [flashId, setFlashId] = useState<string>('')
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const jobs = useJobsStore((s) => s.items)
  const bindSocket = useJobsStore((s) => s.bindSocket)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/v1/course-tools/history', {
        params: { limit: 500, ...(scopeParams || {}) },
      })
      setItems(res.data as LibItem[])
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('tools.load_failed'))
    } finally {
      setLoading(false)
    }
  }

  const clearScopeFilter = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('for_user_id')
    setSearchParams(params, { replace: true })
  }

  useEffect(() => {
    bindSocket()
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [forUserId])

  // Refresh when jobs list changes (job completed → new data available)
  useEffect(() => {
    if (jobs.some((j) => j.status === 'completed')) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.filter((j) => j.status === 'completed').length])

  // ?highlight=<result_id>&tool=<tool_type> → 自动滚到那张卡片并闪一下 ring。
  // 等 items 加载好之后才能找到对应 DOM；待要 highlight 的那条若还在 pending，
  // 切到 pending 子页签让它一定可见。
  useEffect(() => {
    if (!highlightId || !items.length) return
    const target = items.find((it) => it.id === highlightId)
    if (target) {
      if (target.status !== 'completed') setTab('pending')
      else if (highlightTool && tab === 'all') setTab(highlightTool as Tab)
    }
    const node = cardRefs.current[highlightId]
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setFlashId(highlightId)
      const tm = setTimeout(() => setFlashId(''), 2200)
      // 高亮一次后清掉 query，避免每次回到这个页面又闪一次
      const sp = new URLSearchParams(searchParams)
      sp.delete('highlight')
      sp.delete('tool')
      setSearchParams(sp, { replace: true })
      return () => clearTimeout(tm)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightId, items])

  const counts = useMemo(() => {
    const out: Record<ToolType | 'all' | 'pending', number> = {
      all: items.length,
      outline: 0, ppt: 0, exercises: 0, practice: 0,
      pending: 0,
    }
    for (const i of items) {
      out[i.tool_type] = (out[i.tool_type] || 0) + 1
      if (i.status === 'pending' || i.status === 'running' || i.status === 'failed') out.pending += 1
    }
    return out
  }, [items])

  const filtered = useMemo(() => {
    if (tab === 'all') return items
    if (tab === 'pending') return items.filter((i) => i.status !== 'completed')
    return items.filter((i) => i.tool_type === tab)
  }, [items, tab])

  const handleView = (it: LibItem) => {
    const base = `/course-tools?tab=${it.tool_type}&result_id=${it.id}`
    navigate(forUserId ? `${base}&for_user_id=${encodeURIComponent(forUserId)}` : base)
  }

  const handleDelete = async (it: LibItem) => {
    if (!window.confirm(t('tools.confirm_delete'))) return
    try {
      await api.delete(`/api/v1/course-tools/results/${it.id}`, { params: scopeParams })
      setItems((prev) => prev.filter((p) => p.id !== it.id))
      toast.success(t('tools.delete_success'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('tools.delete_failed'))
    }
  }

  const downloadBlob = async (url: string, fallback: string) => {
    try {
      const res = await api.get(url, {
        params: scopeParams,
        responseType: 'blob',
      })
      const objectUrl = URL.createObjectURL(res.data)
      const disp = res.headers['content-disposition'] || ''
      const m = disp.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i)
      const fname = m ? decodeURIComponent(m[1].replace(/"/g, '')) : fallback
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = fname
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(objectUrl)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('tools.download_failed'))
    }
  }

  const handleDownload = (it: LibItem) => {
    if (it.status !== 'completed') {
      toast.info(t('tools.not_ready_yet'))
      return
    }
    switch (it.tool_type) {
      case 'outline':
        downloadBlob(`/api/v1/course-tools/outline/${it.id}/download`, 'outline.docx'); break
      case 'ppt':
        downloadBlob(`/api/v1/course-tools/ppt/${it.id}/download`, 'slides.pptx'); break
      case 'exercises':
        downloadBlob(`/api/v1/course-tools/exercises/${it.id}/download?version=student`, 'exercises.docx'); break
      case 'practice':
        downloadBlob(`/api/v1/course-tools/practice/${it.id}/download`, 'practice.docx'); break
    }
  }

  const TABS: { key: Tab; icon: typeof Layers; labelKey: string; color: string }[] = [
    { key: 'all', icon: Layers, labelKey: 'tools.library_tab_all', color: 'text-gray-700' },
    { key: 'outline', icon: FileText, labelKey: 'tools.tab_outline', color: 'text-blue-600' },
    { key: 'ppt', icon: Presentation, labelKey: 'tools.tab_ppt', color: 'text-purple-600' },
    { key: 'exercises', icon: ClipboardList, labelKey: 'tools.tab_exercises', color: 'text-green-600' },
    { key: 'practice', icon: Dumbbell, labelKey: 'tools.tab_practice', color: 'text-orange-600' },
    { key: 'pending', icon: Clock, labelKey: 'tools.library_tab_pending', color: 'text-amber-600' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600">{t('tools.dashboard')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('tools.library_title')}</span>
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
            <h1 className="text-2xl font-bold text-gray-900">{t('tools.library_title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('tools.library_subtitle')}</p>
          </div>
          <Link to="/course-tools">
            <Button>{t('tools.go_to_tools')}</Button>
          </Link>
        </div>

        <div className="flex flex-wrap gap-1.5 bg-white rounded-xl border p-1.5 mb-5">
          {TABS.map((tb) => {
            const Icon = tb.icon
            const active = tab === tb.key
            const count = counts[tb.key as ToolType | 'all' | 'pending']
            return (
              <button
                key={tb.key}
                onClick={() => setTab(tb.key)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                  active ? 'bg-brand-600 text-white shadow-sm' : `${tb.color} hover:bg-gray-50`
                }`}
              >
                <Icon className="w-4 h-4" />
                {t(tb.labelKey)}
                <span className={`text-[11px] px-1.5 rounded-full ${active ? 'bg-white/20' : 'bg-gray-100'}`}>
                  {count || 0}
                </span>
              </button>
            )
          })}
        </div>

        {loading ? (
          <div className="py-20 text-center">
            <Loader2 className="w-8 h-8 mx-auto animate-spin text-brand-500" />
          </div>
        ) : filtered.length === 0 ? (
          <Card className="py-16 text-center text-sm text-gray-400">
            <div className="mb-2">{t('tools.library_empty')}</div>
            <Link to="/course-tools" className="text-brand-600 hover:underline text-sm">
              {t('tools.go_to_tools')} →
            </Link>
          </Card>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filtered.map((it) => {
              const meta = TOOL_META[it.tool_type]
              const Icon = meta.icon
              const isFlashing = flashId === it.id
              return (
                <div
                  key={it.id}
                  ref={(el) => { cardRefs.current[it.id] = el }}
                  className={
                    isFlashing
                      ? 'ring-2 ring-brand-500 ring-offset-2 rounded-xl transition-all duration-300 animate-pulse'
                      : ''
                  }
                >
                <Card padding={false} className="group hover:shadow-md hover:border-brand-200 transition-all">
                  <div className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${meta.color}`}>
                        <Icon className="w-3.5 h-3.5" />
                        {t(meta.labelKey)}
                      </div>
                      <StatusPill status={it.status} t={t} />
                    </div>
                    <h3 className="font-semibold text-gray-900 truncate mb-1">
                      {it.title || t(meta.labelKey)}
                    </h3>
                    <p className="text-xs text-gray-400">
                      {new Date(it.created_at).toLocaleString()}
                    </p>
                    {it.status === 'failed' && it.error_message && (
                      <p className="text-xs text-red-500 mt-2 line-clamp-2">{it.error_message}</p>
                    )}

                    <div className="mt-3 flex items-center gap-2">
                      <button
                        onClick={() => handleView(it)}
                        className="flex items-center gap-1 text-xs text-brand-600 hover:underline"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        {t('tools.job_view')}
                      </button>
                      {it.status === 'completed' && (
                        <button
                          onClick={() => handleDownload(it)}
                          className="flex items-center gap-1 text-xs text-gray-600 hover:text-brand-600"
                        >
                          <Download className="w-3.5 h-3.5" />
                          {t('tools.download')}
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(it)}
                        className="ml-auto flex items-center gap-1 text-xs text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </Card>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}

function StatusPill({ status, t }: { status: LibItem['status']; t: (k: string) => string }) {
  const map: Record<LibItem['status'], { label: string; color: string; icon: any }> = {
    pending: { label: t('tools.status_pending'), color: 'text-amber-600 bg-amber-50', icon: Clock },
    running: { label: t('tools.status_running'), color: 'text-blue-600 bg-blue-50', icon: Loader2 },
    completed: { label: t('tools.status_completed'), color: 'text-green-600 bg-green-50', icon: CheckCircle2 },
    failed: { label: t('tools.status_failed'), color: 'text-red-600 bg-red-50', icon: AlertTriangle },
  }
  const m = map[status]
  const Icon = m.icon
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${m.color}`}>
      <Icon className={`w-3 h-3 ${status === 'running' ? 'animate-spin' : ''}`} />
      {m.label}
    </div>
  )
}
