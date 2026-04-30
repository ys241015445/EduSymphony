export type AccessLevel = 'full' | 'limited' | 'admin'

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
