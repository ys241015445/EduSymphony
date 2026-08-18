/** Expert → desktop-pet species registry (shared by arena + AgentCard). */

export type PetSpecies =
  | 'owl'
  | 'fox'
  | 'rabbit'
  | 'dolphin'
  | 'cat'
  | 'bear'
  | 'deer'

export type PetState =
  | 'idle'
  | 'thinking'
  | 'speaking'
  | 'listening'
  | 'voting_agree'
  | 'voting_disagree'
  | 'cheer'

export type PetPose =
  | 'idle'
  | 'listen'
  | 'think'
  | 'speak'
  | 'walk'
  | 'vote_yes'
  | 'vote_no'
  | 'cheer'

export interface PetDef {
  role: string
  roleKey: string
  species: PetSpecies
  /** public/pets folder key */
  spriteKey: string
  nicknameKey: string
  primary: string
  secondary: string
  accent: string
  provider?: string
}

/** Five core experts in discussion arc order (left → right). */
export const CORE_EXPERT_ROLES = [
  '教案优化专家',
  '学生参与专家',
  '创新教学专家',
  '深度学习专家',
  '认知发展专家',
] as const

export const SIDE_ROLES = ['教研主持人', '教案编写专家'] as const

export const PET_BY_ROLE: Record<string, PetDef> = {
  教案优化专家: {
    role: '教案优化专家',
    roleKey: 'role.lesson_optimizer',
    species: 'owl',
    spriteKey: 'lesson_optimizer',
    nicknameKey: 'pet.nick.owl',
    primary: '#3B82F6',
    secondary: '#BFDBFE',
    accent: '#1D4ED8',
    provider: 'qwen',
  },
  学生参与专家: {
    role: '学生参与专家',
    roleKey: 'role.student_engagement',
    species: 'fox',
    spriteKey: 'student_engagement',
    nicknameKey: 'pet.nick.fox',
    primary: '#A855F7',
    secondary: '#E9D5FF',
    accent: '#7E22CE',
    provider: 'kimi',
  },
  创新教学专家: {
    role: '创新教学专家',
    roleKey: 'role.innovative_teaching',
    species: 'rabbit',
    spriteKey: 'innovative_teaching',
    nicknameKey: 'pet.nick.rabbit',
    primary: '#F59E0B',
    secondary: '#FDE68A',
    accent: '#B45309',
    provider: 'doubao',
  },
  深度学习专家: {
    role: '深度学习专家',
    roleKey: 'role.deep_learning',
    species: 'dolphin',
    spriteKey: 'deep_learning',
    nicknameKey: 'pet.nick.dolphin',
    primary: '#22C55E',
    secondary: '#BBF7D0',
    accent: '#15803D',
    provider: 'deepseek',
  },
  认知发展专家: {
    role: '认知发展专家',
    roleKey: 'role.cognitive_development',
    species: 'cat',
    spriteKey: 'cognitive_development',
    nicknameKey: 'pet.nick.cat',
    primary: '#F43F5E',
    secondary: '#FECDD3',
    accent: '#BE123C',
    provider: 'spark',
  },
  教研主持人: {
    role: '教研主持人',
    roleKey: 'role.moderator',
    species: 'bear',
    spriteKey: 'moderator',
    nicknameKey: 'pet.nick.bear',
    primary: '#6366F1',
    secondary: '#C7D2FE',
    accent: '#4338CA',
  },
  教案编写专家: {
    role: '教案编写专家',
    roleKey: 'role.writer',
    species: 'deer',
    spriteKey: 'writer',
    nicknameKey: 'pet.nick.deer',
    primary: '#14B8A6',
    secondary: '#99F6E4',
    accent: '#0F766E',
  },
}

export function getPetDef(role: string): PetDef | null {
  return PET_BY_ROLE[role] || null
}

export function petStateToPose(state: PetState, opts?: { walking?: boolean }): PetPose {
  if (opts?.walking) {
    if (state === 'speaking' || state === 'thinking' || state === 'idle') return 'walk'
  }
  switch (state) {
    case 'speaking':
      return 'speak'
    case 'thinking':
      return 'think'
    case 'listening':
      return 'listen'
    case 'voting_agree':
      return 'vote_yes'
    case 'voting_disagree':
      return 'vote_no'
    case 'cheer':
      return 'cheer'
    default:
      return 'idle'
  }
}

/** Arc seat positions in a 400×220 stage (origin top-left). Center stage for speaking. */
export const SEAT_LAYOUT: { x: number; y: number }[] = [
  { x: 28, y: 78 },
  { x: 100, y: 48 },
  { x: 172, y: 36 },
  { x: 244, y: 48 },
  { x: 316, y: 78 },
]

export const STAGE_CENTER = { x: 172, y: 100 }
export const STAGE_SIZE = { w: 400, h: 220 }
