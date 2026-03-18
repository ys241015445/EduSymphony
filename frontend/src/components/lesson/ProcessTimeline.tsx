import { CheckCircle2, Circle, Loader2, Clock } from 'lucide-react'
import clsx from 'clsx'

export interface TimelineEvent {
  id: string
  type: 'started' | 'planning' | 'section_start' | 'analysis' | 'vote_complete' | 'section_done' | 'completed' | 'failed'
  label: string
  detail?: string
  timestamp?: string
  elapsed?: string
}

interface Props {
  events: TimelineEvent[]
  activeIndex: number
}

const typeIcons: Record<string, { icon: any; color: string }> = {
  started: { icon: Clock, color: 'text-gray-400 bg-gray-100' },
  planning: { icon: Loader2, color: 'text-blue-500 bg-blue-50' },
  section_start: { icon: Circle, color: 'text-brand-500 bg-brand-50' },
  analysis: { icon: Circle, color: 'text-purple-500 bg-purple-50' },
  vote_complete: { icon: CheckCircle2, color: 'text-amber-500 bg-amber-50' },
  section_done: { icon: CheckCircle2, color: 'text-green-500 bg-green-50' },
  completed: { icon: CheckCircle2, color: 'text-green-600 bg-green-50' },
  failed: { icon: Circle, color: 'text-red-500 bg-red-50' },
}

export default function ProcessTimeline({ events, activeIndex }: Props) {
  return (
    <div className="space-y-0">
      {events.map((ev, i) => {
        const cfg = typeIcons[ev.type] || typeIcons.started
        const Icon = cfg.icon
        const isActive = i === activeIndex
        const isDone = i < activeIndex

        return (
          <div key={ev.id} className="relative flex gap-3">
            {/* Vertical line */}
            {i < events.length - 1 && (
              <div className="absolute left-[15px] top-8 bottom-0 w-px bg-gray-200" />
            )}

            {/* Icon */}
            <div className={clsx(
              'relative z-10 w-[30px] h-[30px] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
              isDone ? 'bg-green-50' : cfg.color.split(' ')[1],
            )}>
              {isDone ? (
                <CheckCircle2 className="w-4 h-4 text-green-500" />
              ) : isActive && ev.type !== 'completed' ? (
                <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />
              ) : (
                <Icon className={clsx('w-4 h-4', isDone ? 'text-green-500' : cfg.color.split(' ')[0])} />
              )}
            </div>

            {/* Content */}
            <div className={clsx('flex-1 pb-5 min-w-0', isActive && 'font-medium')}>
              <div className="flex items-center justify-between gap-2">
                <span className={clsx(
                  'text-sm truncate',
                  isActive ? 'text-gray-900' : isDone ? 'text-gray-600' : 'text-gray-400'
                )}>
                  {ev.label}
                </span>
                {ev.timestamp && (
                  <span className="text-xs text-gray-400 flex-shrink-0">{ev.timestamp}</span>
                )}
              </div>
              {ev.detail && (
                <p className="text-xs text-gray-400 mt-0.5 truncate">{ev.detail}</p>
              )}
              {ev.elapsed && (
                <span className="inline-block mt-1 text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
                  {ev.elapsed}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
