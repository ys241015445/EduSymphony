import { useState } from 'react'
import { User, ChevronDown, ChevronUp, RefreshCw, ThumbsUp, ThumbsDown } from 'lucide-react'
import clsx from 'clsx'
import { useT } from '../../i18n/translations'
import StreamingText from './StreamingText'

interface VoteDetail {
  voter: string
  vote: 'agree' | 'disagree'
  reason: string
}

interface VotesData {
  summary?: { agree: number; disagree: number }
  details?: VoteDetail[]
  agree?: number
  disagree?: number
}

interface Props {
  role: string
  opinion?: string
  streamingText?: string
  isStreaming?: boolean
  isAccepted?: boolean
  votes?: VotesData | null
  timestamp?: string
  compact?: boolean
  provider?: string
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: () => void
  onRegenerate?: () => void
  isRegenerating?: boolean
}

const roleColors: Record<string, string> = {
  '课程设计专家': 'bg-blue-50 text-blue-700 border-blue-200',
  '学科专家': 'bg-purple-50 text-purple-700 border-purple-200',
  '教学法专家': 'bg-amber-50 text-amber-700 border-amber-200',
  '评估专家': 'bg-green-50 text-green-700 border-green-200',
  '技术整合专家': 'bg-rose-50 text-rose-700 border-rose-200',
  '教研主持人': 'bg-indigo-50 text-indigo-700 border-indigo-200',
  '教案编写专家': 'bg-teal-50 text-teal-700 border-teal-200',
  '教案优化专家': 'bg-blue-50 text-blue-700 border-blue-200',
  '学生参与专家': 'bg-purple-50 text-purple-700 border-purple-200',
  '创新教学专家': 'bg-amber-50 text-amber-700 border-amber-200',
  '深度学习专家': 'bg-green-50 text-green-700 border-green-200',
  '认知发展专家': 'bg-rose-50 text-rose-700 border-rose-200',
}

export const ROLE_KEY_MAP: Record<string, string> = {
  '教案优化专家': 'role.lesson_optimizer',
  '学生参与专家': 'role.student_engagement',
  '创新教学专家': 'role.innovative_teaching',
  '深度学习专家': 'role.deep_learning',
  '认知发展专家': 'role.cognitive_development',
  '课程设计专家': 'role.curriculum_designer',
  '学科专家': 'role.subject_expert',
  '教学法专家': 'role.pedagogy_expert',
  '评估专家': 'role.assessment_expert',
  '技术整合专家': 'role.tech_integration',
  '教研主持人': 'role.moderator',
  '教案编写专家': 'role.writer',
}

export const PROVIDER_KEYS: Record<string, string> = {
  qwen: 'provider.qwen',
  kimi: 'provider.kimi',
  doubao: 'provider.doubao',
  deepseek: 'provider.deepseek',
  spark: 'provider.spark',
  openai: 'provider.openai',
}

export default function AgentCard({
  role, opinion, streamingText, isStreaming,
  isAccepted, votes, timestamp, compact, provider,
  selectable, selected, onToggleSelect, onRegenerate, isRegenerating,
}: Props) {
  const t = useT()
  const [expanded, setExpanded] = useState(false)
  const [showVoteDetails, setShowVoteDetails] = useState(false)
  const colorClass = roleColors[role] || 'bg-gray-50 text-gray-700 border-gray-200'
  const showStreaming = isStreaming || (streamingText !== undefined && streamingText !== null)
  const displayText = showStreaming ? (streamingText || '') : (opinion || '')

  const isLongText = displayText.length > 300

  const agreeCount = votes?.summary?.agree ?? votes?.agree ?? 0
  const disagreeCount = votes?.summary?.disagree ?? votes?.disagree ?? 0
  const totalVotes = agreeCount + disagreeCount
  const hasVotes = totalVotes > 0
  const voteDetails: VoteDetail[] = votes?.details || []

  return (
    <div className={clsx(
      'rounded-xl border transition-all duration-200',
      isAccepted ? 'border-brand-300 bg-brand-50/30 shadow-sm' :
        isStreaming ? 'border-brand-200 bg-white shadow-sm ring-1 ring-brand-100' :
        'border-gray-200 bg-white',
      compact ? 'p-3' : 'p-4',
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {selectable && (
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggleSelect}
              className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
          )}
          <div className={clsx('w-7 h-7 rounded-full flex items-center justify-center', colorClass.split(' ')[0])}>
            <User className={clsx('w-3.5 h-3.5', colorClass.split(' ')[1])} />
          </div>
          <span className={clsx(
            'text-sm font-medium',
            isAccepted ? 'text-brand-700' : 'text-gray-900',
          )}>
            {ROLE_KEY_MAP[role] ? t(ROLE_KEY_MAP[role]) : role}
          </span>
          {provider && PROVIDER_KEYS[provider] && (
            <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-mono">
              {t(PROVIDER_KEYS[provider])}
            </span>
          )}
          {isStreaming && (
            <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full font-medium animate-pulse">
              {t('comp.generating_label')}
            </span>
          )}
          {isAccepted && (
            <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full font-medium">
              {t('comp.accepted')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {timestamp && <span className="text-xs text-gray-400">{timestamp}</span>}
          {onRegenerate && !isStreaming && (
            <button
              onClick={onRegenerate}
              disabled={isRegenerating}
              className={clsx(
                'flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border transition-colors',
                isRegenerating
                  ? 'border-gray-200 text-gray-400 cursor-not-allowed'
                  : 'border-orange-200 text-orange-600 hover:bg-orange-50',
              )}
            >
              <RefreshCw className={clsx('w-3 h-3', isRegenerating && 'animate-spin')} />
              {t('comp.regenerate')}
            </button>
          )}
        </div>
      </div>

      {showStreaming ? (
        <StreamingText
          text={displayText}
          isStreaming={!!isStreaming}
          className="text-gray-600"
          maxHeight={compact ? '120px' : expanded ? 'none' : '240px'}
        />
      ) : (
        <div className={clsx(
          'text-sm text-gray-600 leading-relaxed whitespace-pre-wrap',
          !expanded && (compact ? 'line-clamp-3' : 'line-clamp-6'),
        )}>
          {displayText}
        </div>
      )}

      {isLongText && !showStreaming && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-2 flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? t('comp.collapse') : t('comp.expand')}
        </button>
      )}

      {/* Vote summary bar + details toggle */}
      {hasVotes && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <ThumbsUp className="w-3.5 h-3.5 text-green-500" />
              <span className="text-xs font-semibold text-green-600">{agreeCount}</span>
            </div>
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-400 to-green-500 rounded-full transition-all duration-500"
                style={{ width: `${(agreeCount / totalVotes) * 100}%` }}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-red-500">{disagreeCount}</span>
              <ThumbsDown className="w-3.5 h-3.5 text-red-400" />
            </div>
          </div>

          {voteDetails.length > 0 && (
            <button
              onClick={() => setShowVoteDetails(!showVoteDetails)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-brand-600 transition-colors"
            >
              {showVoteDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {t('comp.vote_detail')} ({totalVotes}{t('comp.vote_unit')})
            </button>
          )}

          {showVoteDetails && voteDetails.length > 0 && (
            <div className="bg-gray-50 rounded-lg p-3 space-y-2 border border-gray-100">
              {voteDetails.map((vd, vi) => (
                <div key={vi} className="flex items-start gap-2">
                  <div className="flex-shrink-0 mt-0.5">
                    {vd.vote === 'agree' ? (
                      <ThumbsUp className="w-3 h-3 text-green-500" />
                    ) : (
                      <ThumbsDown className="w-3 h-3 text-red-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-gray-700">{ROLE_KEY_MAP[vd.voter] ? t(ROLE_KEY_MAP[vd.voter]) : vd.voter}</span>
                      <span className={clsx(
                        'text-[10px] font-medium px-1.5 py-0.5 rounded-full',
                        vd.vote === 'agree'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-600',
                      )}>
                        {vd.vote === 'agree' ? t('comp.vote_agree') : t('comp.vote_disagree')}
                      </span>
                    </div>
                    {vd.reason && (
                      <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{vd.reason}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
