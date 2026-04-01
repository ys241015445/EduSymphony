import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { useT } from '../../i18n/translations'

export interface Section {
  key: string
  name: string
  modelKey?: string
  modelName?: string
  status: 'pending' | 'processing' | 'done'
  content?: string
  expert?: string
}

interface Props {
  sections: Section[]
  activeKey: string | null
  onSelect: (key: string) => void
}

const STATUS_STYLE = {
  pending: 'text-gray-400 bg-gray-100',
  processing: 'text-orange-600 bg-orange-50',
  done: 'text-green-600 bg-green-50',
} as const

const STATUS_KEY = {
  pending: 'section.status_pending',
  processing: 'section.status_processing',
  done: 'section.status_done',
} as const

const BORDER_PALETTE = [
  'border-l-blue-400',
  'border-l-emerald-400',
  'border-l-violet-400',
  'border-l-amber-400',
  'border-l-rose-400',
  'border-l-cyan-400',
  'border-l-fuchsia-400',
  'border-l-lime-400',
]

const DOT_PALETTE = [
  'bg-blue-400',
  'bg-emerald-400',
  'bg-violet-400',
  'bg-amber-400',
  'bg-rose-400',
  'bg-cyan-400',
  'bg-fuchsia-400',
  'bg-lime-400',
]

export default function SectionPanel({ sections, activeKey, onSelect }: Props) {
  const t = useT()
  const groups: { modelKey: string; modelName: string; items: Section[] }[] = []
  let currentGroup: typeof groups[0] | null = null

  for (const s of sections) {
    const mk = s.modelKey || ''
    const mn = s.modelName || ''
    if (!currentGroup || currentGroup.modelKey !== mk) {
      currentGroup = { modelKey: mk, modelName: mn, items: [] }
      groups.push(currentGroup)
    }
    currentGroup.items.push(s)
  }

  let globalIdx = 0

  return (
    <div className="space-y-4">
      {groups.map((g, groupIdx) => (
        <div key={g.modelKey || `group-${groupIdx}`}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className={clsx(
              'w-2 h-2 rounded-full',
              DOT_PALETTE[groupIdx % DOT_PALETTE.length],
            )} />
            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
              {g.modelName}
            </span>
          </div>
          <div className="space-y-1.5">
            {g.items.map((s) => {
              const idx = globalIdx++
              const isActive = s.key === activeKey
              const statusStyle = STATUS_STYLE[s.status]
              const statusLabel = t(STATUS_KEY[s.status])
              const borderColor = BORDER_PALETTE[groupIdx % BORDER_PALETTE.length]

              return (
                <button
                  key={s.key}
                  onClick={() => onSelect(s.key)}
                  className={clsx(
                    'w-full text-left p-2.5 rounded-lg border-l-[3px] border border-gray-200 transition-all duration-200',
                    borderColor,
                    isActive
                      ? 'bg-brand-50/50 shadow-sm ring-1 ring-brand-200'
                      : 'bg-white hover:bg-gray-50 hover:shadow-sm',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div className="flex-shrink-0">
                      {s.status === 'done' ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                      ) : s.status === 'processing' ? (
                        <Loader2 className="w-3.5 h-3.5 text-orange-500 animate-spin" />
                      ) : (
                        <Circle className="w-3.5 h-3.5 text-gray-300" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className={clsx(
                        'text-xs font-medium truncate block',
                        s.status === 'done' ? 'text-gray-900' : s.status === 'processing' ? 'text-brand-700' : 'text-gray-500',
                      )}>
                        {s.name}
                      </span>
                    </div>
                    <div className="flex-shrink-0">
                      <span className={clsx(
                        'inline-flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded-full',
                        statusStyle,
                      )}>
                        {s.status === 'processing' && (
                          <Loader2 className="w-2 h-2 animate-spin" />
                        )}
                        {statusLabel}
                      </span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
