import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Loader2, FileText, Presentation, ClipboardList, Dumbbell, ExternalLink, AlertTriangle } from 'lucide-react'
import { useJobsStore, ToolType } from '../../stores/jobsStore'
import { useT } from '../../i18n/translations'

const ICON: Record<ToolType, typeof FileText> = {
  outline: FileText,
  ppt: Presentation,
  exercises: ClipboardList,
  practice: Dumbbell,
}

export default function JobsBadge() {
  const t = useT()
  const items = useJobsStore((s) => s.items)
  const initialized = useJobsStore((s) => s.initialized)
  const refresh = useJobsStore((s) => s.refreshFromServer)
  const bindSocket = useJobsStore((s) => s.bindSocket)
  const remove = useJobsStore((s) => s.remove)

  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bindSocket()
    if (!initialized) refresh()
  }, [bindSocket, initialized, refresh])

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const active = items.filter((i) => i.status === 'queued' || i.status === 'running')
  const total = active.length

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center w-9 h-9 rounded-lg text-gray-500 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        aria-label={t('jobs.badge_title')}
      >
        <Bell className="w-4 h-4" />
        {total > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold flex items-center justify-center">
            {total > 99 ? '99+' : total}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-50">
          <div className="px-4 py-2 flex items-center justify-between border-b border-gray-100">
            <div className="text-sm font-semibold text-gray-800">{t('jobs.badge_title')}</div>
            <Link
              to="/course-tools/library"
              onClick={() => setOpen(false)}
              className="text-xs text-brand-600 hover:underline flex items-center gap-1"
            >
              {t('tools.go_to_library')}
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-gray-400">{t('tools.no_active_jobs')}</div>
            ) : (
              items.map((it) => {
                const Icon = ICON[it.tool_type] || FileText
                return (
                  <div
                    key={it.result_id}
                    className="px-4 py-2.5 flex items-start gap-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0"
                  >
                    <div
                      className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${
                        it.status === 'failed'
                          ? 'bg-red-50 text-red-600'
                          : it.status === 'completed'
                            ? 'bg-green-50 text-green-600'
                            : 'bg-brand-50 text-brand-600'
                      }`}
                    >
                      {it.status === 'failed' ? (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      ) : it.status === 'running' || it.status === 'queued' ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Icon className="w-3.5 h-3.5" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gray-800 truncate">
                        {it.title || t(`tools.tab_${it.tool_type}`)}
                      </div>
                      <div className="text-[11px] text-gray-500 mt-0.5">
                        {it.status === 'queued' && t('tools.job_queued')}
                        {it.status === 'running' && t('tools.job_running')}
                        {it.status === 'completed' && t('tools.job_completed')}
                        {it.status === 'failed' && (it.error || t('tools.job_failed'))}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Link
                        to={`/course-tools/library?highlight=${it.result_id}&tool=${it.tool_type}`}
                        onClick={() => setOpen(false)}
                        className="text-[11px] text-brand-600 hover:underline"
                      >
                        {t('tools.job_view')}
                      </Link>
                      {(it.status === 'completed' || it.status === 'failed') && (
                        <button
                          onClick={() => remove(it.result_id)}
                          className="text-[11px] text-gray-400 hover:text-gray-600"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
