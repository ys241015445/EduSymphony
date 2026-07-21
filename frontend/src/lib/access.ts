export type AccessLevel = 'full' | 'limited' | 'admin'

export type CapabilityFlag =
  | 'can_course_tools'
  | 'can_template_fill'
  | 'can_university'
  | 'can_series'
  | 'can_next_lesson'
  | 'can_export'
  | 'can_semester_helper'

export const CAPABILITY_FLAGS: CapabilityFlag[] = [
  'can_course_tools',
  'can_template_fill',
  'can_university',
  'can_series',
  'can_next_lesson',
  'can_export',
  'can_semester_helper',
]

/** Per-flag default for users where the column is missing/null (legacy rows). */
export const CAPABILITY_DEFAULTS: Record<CapabilityFlag, boolean> = {
  can_course_tools: true,
  can_template_fill: true,
  can_university: true,
  can_series: true,
  can_next_lesson: true,
  can_export: true,
  can_semester_helper: false,
}

export function parseAccessLevel(v: string | undefined | null): AccessLevel {
  if (v === 'limited' || v === 'admin' || v === 'full') return v
  return 'full'
}

export function canUseCourseTools(level: AccessLevel): boolean {
  return level === 'full' || level === 'admin'
}

export function isAdmin(level: AccessLevel): boolean {
  return level === 'admin'
}

export function isLimited(level: AccessLevel): boolean {
  return level === 'limited'
}

type UserLike = {
  access_level?: string | null
  can_course_tools?: boolean | null
  can_template_fill?: boolean | null
  can_university?: boolean | null
  can_series?: boolean | null
  can_next_lesson?: boolean | null
  can_export?: boolean | null
  can_semester_helper?: boolean | null
} | null | undefined

export function hasCapability(user: UserLike, flag: CapabilityFlag): boolean {
  if (!user) return false
  if (isAdmin(parseAccessLevel(user.access_level))) return true
  const v = user[flag]
  if (v === undefined || v === null) return CAPABILITY_DEFAULTS[flag]
  return !!v
}
