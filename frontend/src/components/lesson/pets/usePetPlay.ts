/** Local play moods (pet / feed) — does not touch Socket stream state. */

import { useCallback, useRef, useState } from 'react'
import type { PetState } from './petRegistry'

export type PlayMood = 'petted' | 'fed' | null

const HOLD_MS = 1600

export function usePetPlay() {
  const [moodByRole, setMoodByRole] = useState<Record<string, PlayMood>>({})
  const [playBubbleByRole, setPlayBubbleByRole] = useState<Record<string, string>>({})
  const timers = useRef<Record<string, number>>({})

  const clearRole = useCallback((role: string) => {
    if (timers.current[role]) window.clearTimeout(timers.current[role])
    delete timers.current[role]
  }, [])

  const apply = useCallback(
    (role: string, mood: PlayMood, bubble: string) => {
      clearRole(role)
      setMoodByRole((m) => ({ ...m, [role]: mood }))
      setPlayBubbleByRole((b) => ({ ...b, [role]: bubble }))
      timers.current[role] = window.setTimeout(() => {
        setMoodByRole((m) => ({ ...m, [role]: null }))
        setPlayBubbleByRole((b) => {
          const next = { ...b }
          delete next[role]
          return next
        })
        delete timers.current[role]
      }, HOLD_MS)
    },
    [clearRole],
  )

  const pet = useCallback(
    (role: string, bubble: string) => apply(role, 'petted', bubble),
    [apply],
  )

  const feed = useCallback(
    (role: string, bubble: string) => apply(role, 'fed', bubble),
    [apply],
  )

  /** Overlay play mood onto stream state; never override speaking/thinking/voting/cheer. */
  const mergeState = useCallback(
    (role: string, streamState: PetState): PetState => {
      const mood = moodByRole[role]
      if (!mood) return streamState
      if (
        streamState === 'speaking' ||
        streamState === 'thinking' ||
        streamState === 'voting_agree' ||
        streamState === 'voting_disagree' ||
        streamState === 'cheer'
      ) {
        return streamState
      }
      return mood === 'fed' ? 'cheer' : 'idle'
    },
    [moodByRole],
  )

  const mergeBubble = useCallback(
    (role: string, streamBubble?: string) => playBubbleByRole[role] || streamBubble,
    [playBubbleByRole],
  )

  return { pet, feed, mergeState, mergeBubble, moodByRole }
}

export const SNACKS = [
  { id: 'fish', emoji: '🐟', labelKey: 'pet.snack.fish' },
  { id: 'carrot', emoji: '🥕', labelKey: 'pet.snack.carrot' },
  { id: 'cookie', emoji: '🍪', labelKey: 'pet.snack.cookie' },
] as const
