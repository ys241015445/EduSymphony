import { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import clsx from 'clsx'
import type { PetDef, PetState } from './petRegistry'
import { petStateToPose } from './petRegistry'
import SvgPet from './SvgPet'
import { hasSpriteCached, probeSprite, spriteUrl } from './petSprites'

interface Props {
  def: PetDef
  state: PetState
  bubble?: string
  label: string
  size?: number
  walking?: boolean
  onClick?: () => void
  className?: string
  /** Outer motion handled by parent */
  bare?: boolean
  groundShadow?: boolean
  /** Use non-button root so parent can own drag/click */
  passive?: boolean
}

export default function PetActor({
  def,
  state,
  bubble,
  label,
  size,
  walking = false,
  onClick,
  className,
  bare = false,
  groundShadow = true,
  passive = false,
}: Props) {
  const reduce = useReducedMotion()
  const pose = petStateToPose(state, { walking: walking && !reduce })
  const [useSprite, setUseSprite] = useState(() => hasSpriteCached(def.spriteKey, pose))
  const mouthOpen = state === 'speaking' || state === 'thinking'
  const displaySize = size ?? (useSprite ? 80 : 56)
  const showLabel = state === 'speaking' || state === 'thinking' || state === 'cheer'

  useEffect(() => {
    let cancelled = false
    probeSprite(def.spriteKey, pose).then((ok) => {
      if (!cancelled) setUseSprite(ok)
    })
    return () => { cancelled = true }
  }, [def.spriteKey, pose])

  const localPulse = reduce
    ? {}
    : state === 'cheer'
      ? { y: [0, -14, 0], transition: { duration: 0.5, repeat: 2 } }
      : state === 'speaking'
        ? { y: [0, -4, 0], scale: [1, 1.04, 1], transition: { duration: 0.85, repeat: Infinity, ease: 'easeInOut' } }
        : state === 'thinking'
          ? { rotate: [-3, 3, -3], transition: { duration: 1.1, repeat: Infinity, ease: 'easeInOut' } }
          : state === 'voting_agree'
            ? { y: [0, -6, 0], transition: { duration: 0.45, repeat: 1 } }
            : state === 'voting_disagree'
              ? { x: [0, -3, 0], transition: { duration: 0.4, repeat: 1 } }
              : state === 'listening'
                ? { scale: [1, 1.015, 1], transition: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' } }
                : state === 'idle'
                  ? { y: [0, -3, 0], transition: { duration: 2.4, repeat: Infinity, ease: 'easeInOut' } }
                  : {}

  const shadowScale =
    state === 'cheer' ? 0.72
      : state === 'speaking' || state === 'thinking' ? 1.1
        : state === 'voting_agree' ? 0.95
          : 1

  const body = (
    <>
      {bubble && (
        <div className="pointer-events-none absolute -top-7 left-1/2 z-20 max-w-[7.5rem] -translate-x-1/2 truncate rounded-md bg-white/90 px-2 py-0.5 text-[10px] text-gray-700 shadow-sm backdrop-blur-sm">
          {bubble}
        </div>
      )}
      {(state === 'voting_agree' || state === 'voting_disagree') && (
        <div
          className={clsx(
            'pointer-events-none absolute -top-5 right-1 z-20 rounded-full px-1.5 py-0.5 text-[9px] font-semibold text-white/95 opacity-80 shadow-sm',
            state === 'voting_agree' ? 'bg-emerald-500/75' : 'bg-rose-500/75',
          )}
        >
          {state === 'voting_agree' ? '✓' : '✗'}
        </div>
      )}
      <motion.div animate={localPulse} className="relative flex flex-col items-center">
        {groundShadow && (
          <span
            aria-hidden
            className="pointer-events-none absolute bottom-1 left-1/2 z-0 h-3 w-[62%] rounded-[100%] bg-black/25 blur-[4px] transition-transform duration-300"
            style={{
              transform: `translateX(-50%) scaleX(${shadowScale}) scaleY(${0.85 + shadowScale * 0.15})`,
            }}
          />
        )}
        <div className="relative z-10">
          {useSprite ? (
            <img
              src={spriteUrl(def.spriteKey, pose)}
              alt=""
              width={displaySize}
              height={displaySize}
              className="pointer-events-none object-contain select-none"
              draggable={false}
            />
          ) : (
            <SvgPet
              species={def.species}
              primary={def.primary}
              secondary={def.secondary}
              accent={def.accent}
              mouthOpen={mouthOpen && !reduce}
              size={displaySize}
            />
          )}
          {state === 'thinking' && !reduce && (
            <span className="pointer-events-none absolute -right-1 top-0 text-xs animate-pulse opacity-70">…</span>
          )}
        </div>
      </motion.div>
      <span
        className={clsx(
          'mt-0.5 max-w-[5.5rem] truncate text-center text-[10px] font-medium text-gray-600/80 transition-opacity duration-200',
          showLabel
            ? 'opacity-100'
            : 'opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100',
        )}
      >
        {label}
      </span>
    </>
  )

  const rootClass = clsx(
    'group relative flex flex-col items-center gap-0 rounded-xl px-0.5 py-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/50',
    state === 'speaking' || state === 'cheer' || state === 'voting_agree' ? 'z-20' : 'z-10',
    className,
  )

  if (passive) {
    return (
      <div className={rootClass} aria-label={label} title={label}>
        {body}
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={rootClass}
      aria-label={label}
      title={label}
    >
      {body}
    </button>
  )
}
