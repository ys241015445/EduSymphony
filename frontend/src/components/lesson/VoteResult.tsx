import { ThumbsUp, ThumbsDown } from 'lucide-react'
import { useT } from '../../i18n/translations'

interface Props {
  agree: number
  disagree: number
  acceptedRole: string
  passRate: number
}

export default function VoteResult({ agree, disagree, acceptedRole, passRate }: Props) {
  const t = useT()
  const total = agree + disagree
  const pct = total > 0 ? Math.round((agree / total) * 100) : 0

  return (
    <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">{t('comp.vote_result')}</span>
        <span className="text-xs text-brand-600 font-medium">{acceptedRole}</span>
      </div>

      <div className="flex items-center gap-3 mb-2">
        <div className="flex items-center gap-1 text-green-600">
          <ThumbsUp className="w-3.5 h-3.5" />
          <span className="text-sm font-medium">{agree}</span>
        </div>
        <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className="h-full bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex items-center gap-1 text-red-500">
          <ThumbsDown className="w-3.5 h-3.5" />
          <span className="text-sm font-medium">{disagree}</span>
        </div>
      </div>

      <div className="text-xs text-gray-400 text-center">
        {t('comp.pass_rate')} {Math.round(passRate * 100)}%
      </div>
    </div>
  )
}
