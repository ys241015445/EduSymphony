import { useMemo } from 'react'
import {
  CORE_EXPERT_ROLES,
  SIDE_ROLES,
  getPetDef,
  type PetState,
} from './petRegistry'

export interface StreamBuf {
  agentRole: string
  text: string
  phase: string
  provider?: string
  done: boolean
}

export interface StageVoteInfo {
  accepted_role?: string
  agree?: number
  disagree?: number
  pass_rate?: number
}

export type PetChoreographyPhase =
  | 'idle'
  | 'analysis'
  | 'voting'
  | 'vote_result'
  | 'writing'

interface Input {
  streamBuffers: Record<string, StreamBuf>
  activeStageNum: number
  stageVote?: StageVoteInfo | null
  fullDraftStreaming?: boolean
  fullOptimizedStreaming?: boolean
  isQuickMode?: boolean
}

export interface PetStageSnapshot {
  states: Record<string, PetState>
  bubbles: Record<string, string>
  visibleSide: string[]
  speakingRole: string | null
  /** All roles currently streaming analysis / vote / host talk */
  speakingRoles: string[]
  phase: PetChoreographyPhase
  acceptedRole: string | null
  activeStageNum: number
}

function tailBubble(text: string, n = 24): string {
  const t = (text || '').replace(/\s+/g, ' ').trim()
  if (!t) return '…'
  return t.length <= n ? t : `…${t.slice(-n)}`
}

const emptySnapshot = (activeStageNum: number): PetStageSnapshot => {
  const states: Record<string, PetState> = {}
  for (const role of CORE_EXPERT_ROLES) states[role] = 'idle'
  for (const role of SIDE_ROLES) states[role] = 'idle'
  return {
    states,
    bubbles: {},
    visibleSide: [],
    speakingRole: null,
    speakingRoles: [],
    phase: 'idle',
    acceptedRole: null,
    activeStageNum,
  }
}

/** Derive per-role pet states from existing LessonProcess stream/vote state. */
export function usePetStage({
  streamBuffers,
  activeStageNum,
  stageVote,
  fullDraftStreaming,
  fullOptimizedStreaming,
  isQuickMode,
}: Input): PetStageSnapshot {
  return useMemo(() => {
    if (isQuickMode) return emptySnapshot(activeStageNum)

    const states: Record<string, PetState> = {}
    const bubbles: Record<string, string> = {}
    for (const role of CORE_EXPERT_ROLES) states[role] = 'idle'
    for (const role of SIDE_ROLES) states[role] = 'idle'

    const stagePrefix = `${activeStageNum}_`
    const stageBufs = Object.entries(streamBuffers)
      .filter(([key]) => key.startsWith(stagePrefix))
      .map(([, b]) => b)

    const bufs =
      stageBufs.length > 0
        ? stageBufs
        : Object.values(streamBuffers).filter((b) =>
            ['analysis', 'expert_vote', 'vote_result', 'finalize'].includes(b.phase),
          )

    const speakingRoles: string[] = []
    let hasOpenAnalysis = false
    let hasVoting = false
    let hasVoteResult = false

    for (const buf of bufs) {
      if (!getPetDef(buf.agentRole)) continue
      if (buf.phase === 'analysis') {
        if (!buf.done) {
          hasOpenAnalysis = true
          states[buf.agentRole] = 'speaking'
          bubbles[buf.agentRole] = tailBubble(buf.text)
          if (!speakingRoles.includes(buf.agentRole)) speakingRoles.push(buf.agentRole)
        } else if (states[buf.agentRole] === 'idle') {
          states[buf.agentRole] = 'listening'
        }
      } else if (buf.phase === 'expert_vote') {
        hasVoting = true
        if (!buf.done) {
          states[buf.agentRole] = 'thinking'
          bubbles[buf.agentRole] = tailBubble(buf.text)
          if (!speakingRoles.includes(buf.agentRole)) speakingRoles.push(buf.agentRole)
        } else {
          const lower = buf.text.toLowerCase()
          const agree =
            /赞成|同意|支持|agree|approve|yes/i.test(buf.text) &&
            !/不赞成|不同意|反对|disagree/i.test(buf.text.slice(0, 40))
          const disagree = /反对|不同意|不赞成|disagree|reject|no/i.test(lower)
          if (agree && !disagree) states[buf.agentRole] = 'voting_agree'
          else if (disagree) states[buf.agentRole] = 'voting_disagree'
          else states[buf.agentRole] = 'listening'
        }
      } else if (buf.phase === 'vote_result') {
        hasVoteResult = true
        states['教研主持人'] = buf.done ? 'listening' : 'speaking'
        if (!buf.done) {
          bubbles['教研主持人'] = tailBubble(buf.text)
          if (!speakingRoles.includes('教研主持人')) speakingRoles.push('教研主持人')
        }
      }
    }

    const speakingRole = speakingRoles.length > 0 ? speakingRoles[speakingRoles.length - 1] : null

    if (speakingRoles.length > 0) {
      for (const role of CORE_EXPERT_ROLES) {
        if (!speakingRoles.includes(role) && states[role] === 'idle') states[role] = 'listening'
      }
    }

    const acceptedRole =
      stageVote?.accepted_role && getPetDef(stageVote.accepted_role)
        ? stageVote.accepted_role
        : null
    if (acceptedRole) states[acceptedRole] = 'cheer'

    const visibleSide: string[] = []
    if (hasVoteResult || stageVote) visibleSide.push('教研主持人')

    const writing = !!(fullDraftStreaming || fullOptimizedStreaming)
    if (writing) {
      visibleSide.push('教案编写专家')
      states['教案编写专家'] = 'speaking'
      bubbles['教案编写专家'] = fullOptimizedStreaming ? '优化中…' : '撰写中…'
      if (!speakingRoles.includes('教案编写专家')) speakingRoles.push('教案编写专家')
      for (const role of CORE_EXPERT_ROLES) {
        if (states[role] === 'idle') states[role] = 'listening'
      }
    } else if (bufs.some((b) => b.phase === 'finalize')) {
      visibleSide.push('教案编写专家')
    }

    // Phase priority: writing > vote_result > voting > analysis > idle
    let phase: PetChoreographyPhase = 'idle'
    if (writing) phase = 'writing'
    else if (hasVoteResult || stageVote) phase = 'vote_result'
    else if (hasVoting) phase = 'voting'
    else if (hasOpenAnalysis || speakingRoles.length > 0) phase = 'analysis'

    return {
      states,
      bubbles,
      visibleSide,
      speakingRole,
      speakingRoles,
      phase,
      acceptedRole,
      activeStageNum,
    }
  }, [
    streamBuffers,
    activeStageNum,
    stageVote,
    fullDraftStreaming,
    fullOptimizedStreaming,
    isQuickMode,
  ])
}
