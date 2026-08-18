import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import clsx from 'clsx'
import { useT } from '../../../i18n/translations'
import {
  CORE_EXPERT_ROLES,
  SIDE_ROLES,
  getPetDef,
  type PetState,
} from './petRegistry'
import PetActor from './PetActor'
import type { PetChoreographyPhase, PetStageSnapshot } from './usePetStage'
import { SNACKS, usePetPlay } from './usePetPlay'

interface Props {
  snapshot: PetStageSnapshot
  onSelectRole?: (role: string) => void
}

type Pos = { x: number; y: number }
type Choreo = { ox: number; oy: number; scale: number; rotateY: number }

const STORAGE_KEY = 'edusymphony.pet.positions.v1'
const DRAG_CLICK_PX = 6
const PET_W = 88
const PET_H = 100
const SECTION_PULSE_MS = 1400

function defaultPositions(w: number, h: number): Record<string, Pos> {
  const baseY = Math.max(100, h - 130)
  const gap = Math.min(100, Math.max(70, (w - 100) / 6))
  const startX = Math.max(20, Math.min(80, w * 0.06))
  const out: Record<string, Pos> = {}
  CORE_EXPERT_ROLES.forEach((role, i) => {
    out[role] = { x: startX + i * gap, y: baseY - (i % 2) * 16 }
  })
  out['教研主持人'] = { x: Math.max(40, w - 140), y: 64 }
  out['教案编写专家'] = { x: Math.max(40, w - 140), y: 160 }
  return out
}

function clampPos(p: Pos, w: number, h: number): Pos {
  return {
    x: Math.min(Math.max(4, p.x), Math.max(4, w - PET_W)),
    y: Math.min(Math.max(4, p.y), Math.max(4, h - PET_H)),
  }
}

function loadPositions(w: number, h: number): Record<string, Pos> {
  const fallback = defaultPositions(w, h)
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return fallback
    const parsed = JSON.parse(raw) as Record<string, Pos>
    const next: Record<string, Pos> = { ...fallback }
    for (const [k, v] of Object.entries(parsed)) {
      if (v && typeof v.x === 'number' && typeof v.y === 'number') {
        next[k] = clampPos(v, w, h)
      }
    }
    return next
  } catch {
    return fallback
  }
}

function savePositions(pos: Record<string, Pos>) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pos))
  } catch {
    /* ignore */
  }
}

function faceYaw(fromX: number, targetX: number | null): number {
  if (targetX == null) return 0
  const dx = targetX - fromX
  if (Math.abs(dx) < 20) return 0
  return dx > 0 ? -16 : 16
}

function choreoForRole(opts: {
  role: string
  index: number
  home: Pos
  center: Pos
  state: PetState
  phase: PetChoreographyPhase
  speakingRoles: string[]
  acceptedRole: string | null
  speakerHomeX: number | null
  sectionPulse: boolean
  dragging: boolean
  reduce: boolean
}): Choreo {
  const zero: Choreo = { ox: 0, oy: 0, scale: 1, rotateY: 0 }
  if (opts.reduce || opts.dragging) return zero

  const {
    home,
    center,
    state,
    phase,
    role,
    index,
    acceptedRole,
    speakerHomeX,
    sectionPulse,
  } = opts

  if (sectionPulse) {
    const jig = ((index % 3) - 1) * 14
    return { ox: jig, oy: -8 - (index % 2) * 6, scale: 1.04, rotateY: 0 }
  }

  // Per-role state first — who speaks / votes moves themselves
  switch (state) {
    case 'speaking':
      return {
        ox: (center.x - home.x) * 0.38,
        oy: (center.y - home.y) * 0.42 - 12,
        scale: 1.16,
        rotateY: 0,
      }
    case 'thinking':
      return {
        ox: Math.sin(index * 1.7) * 6,
        oy: -4,
        scale: 1.02,
        rotateY: faceYaw(home.x, speakerHomeX ?? center.x),
      }
    case 'voting_agree':
      return {
        ox: (center.x - home.x) * 0.18,
        oy: -16,
        scale: 1.08,
        rotateY: faceYaw(home.x, center.x),
      }
    case 'voting_disagree':
      return {
        ox: (home.x - center.x) * 0.12,
        oy: 8,
        scale: 0.95,
        rotateY: faceYaw(home.x, center.x),
      }
    case 'cheer':
      return { ox: 0, oy: -24, scale: 1.18, rotateY: 0 }
    case 'listening':
      return {
        ox: 0,
        oy: 0,
        scale: 0.94,
        rotateY: faceYaw(home.x, speakerHomeX),
      }
    default:
      break
  }

  // Neighbors congratulate accepted pet
  if (phase === 'vote_result' && acceptedRole && role !== acceptedRole) {
    const ai = CORE_EXPERT_ROLES.indexOf(acceptedRole as (typeof CORE_EXPERT_ROLES)[number])
    const ri = CORE_EXPERT_ROLES.indexOf(role as (typeof CORE_EXPERT_ROLES)[number])
    if (ai >= 0 && ri >= 0 && Math.abs(ai - ri) === 1) {
      return { ox: 0, oy: -10, scale: 1.06, rotateY: faceYaw(home.x, speakerHomeX) }
    }
  }

  if (phase === 'writing' && role === '教案编写专家') {
    return { ox: -20, oy: 8, scale: 1.1, rotateY: 0 }
  }

  return zero
}

/** Floating Shimeji-style pets with process-driven choreography. */
export default function PetsDesktopLayer({ snapshot, onSelectRole }: Props) {
  const t = useT()
  const reduce = useReducedMotion()
  const {
    states,
    bubbles,
    visibleSide,
    speakingRole,
    speakingRoles,
    phase,
    acceptedRole,
    activeStageNum,
  } = snapshot
  const { pet, feed, mergeState, mergeBubble } = usePetPlay()

  const layerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 1200, h: 700 })
  const [positions, setPositions] = useState<Record<string, Pos>>(() => defaultPositions(1200, 700))
  const [menuRole, setMenuRole] = useState<string | null>(null)
  const [dragSnack, setDragSnack] = useState<string | null>(null)
  const [draggingRole, setDraggingRole] = useState<string | null>(null)
  const [dragBase, setDragBase] = useState<Record<string, Pos>>({})
  const [sectionPulse, setSectionPulse] = useState(false)
  const [sectionBubbles, setSectionBubbles] = useState<Record<string, string>>({})
  const prevStage = useRef(activeStageNum)
  const dragOrigin = useRef<Record<string, Pos>>({})
  const didDrag = useRef(false)

  const visibleRoles = useMemo(() => {
    const roles: string[] = [...CORE_EXPERT_ROLES]
    for (const r of SIDE_ROLES) {
      if (visibleSide.includes(r)) roles.push(r)
    }
    return roles
  }, [visibleSide])

  const center = useMemo(
    () => ({ x: size.w * 0.52 - PET_W / 2, y: size.h * 0.42 }),
    [size.w, size.h],
  )

  const speakerHomeX = useMemo(() => {
    const focus = speakingRole || speakingRoles[0]
    return focus ? positions[focus]?.x ?? null : null
  }, [speakingRole, speakingRoles, positions])

  // Section change pulse
  useEffect(() => {
    if (prevStage.current === activeStageNum) return
    prevStage.current = activeStageNum
    if (activeStageNum <= 0) return
    setSectionPulse(true)
    const msg = t('pet.phase.next_section')
    const next: Record<string, string> = {}
    for (const role of CORE_EXPERT_ROLES) next[role] = msg
    setSectionBubbles(next)
    const id = window.setTimeout(() => {
      setSectionPulse(false)
      setSectionBubbles({})
    }, SECTION_PULSE_MS)
    return () => window.clearTimeout(id)
  }, [activeStageNum, t])

  useEffect(() => {
    const el = layerRef.current
    if (!el) return
    const measure = () => {
      const r = el.getBoundingClientRect()
      const w = Math.max(320, r.width)
      const h = Math.max(280, r.height)
      setSize({ w, h })
      setPositions(loadPositions(w, h))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!menuRole) return
      const target = e.target as HTMLElement | null
      if (target?.closest('[data-pet-menu]') || target?.closest('[data-pet-actor]')) return
      setMenuRole(null)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menuRole])

  const labelFor = (role: string) => {
    const def = getPetDef(role)
    if (!def) return role
    return `${t(def.nicknameKey)} · ${t(def.roleKey)}`
  }

  const commitPos = useCallback(
    (role: string, x: number, y: number) => {
      setPositions((prev) => {
        const next = { ...prev, [role]: clampPos({ x, y }, size.w, size.h) }
        savePositions(next)
        return next
      })
    },
    [size.w, size.h],
  )

  const hitTestPet = useCallback(
    (clientX: number, clientY: number): string | null => {
      const layer = layerRef.current
      if (!layer) return null
      const rect = layer.getBoundingClientRect()
      const lx = clientX - rect.left
      const ly = clientY - rect.top
      for (const role of [...visibleRoles].reverse()) {
        const p = positions[role]
        if (!p) continue
        if (lx >= p.x && lx <= p.x + PET_W && ly >= p.y && ly <= p.y + PET_H) return role
      }
      return null
    },
    [positions, visibleRoles],
  )

  const doFeed = (role: string) => {
    feed(role, t('pet.bubble.fed'))
    setMenuRole(null)
  }

  const doPet = (role: string) => {
    pet(role, t('pet.bubble.petted'))
    setMenuRole(null)
  }

  return (
    <div
      ref={layerRef}
      className="pointer-events-none absolute inset-0 z-30 overflow-hidden"
      aria-label={t('pet.desktop_aria')}
    >
      {visibleRoles.map((role, index) => {
        const def = getPetDef(role)
        if (!def) return null
        const home = positions[role] || { x: 40, y: 40 }
        const streamState: PetState = states[role] || 'idle'
        const state = mergeState(role, streamState)
        const bubble =
          mergeBubble(role, bubbles[role]) || sectionBubbles[role] || undefined
        const showMenu = menuRole === role
        const isDragging = draggingRole === role
        const c = choreoForRole({
          role,
          index,
          home,
          center,
          state,
          phase,
          speakingRoles,
          acceptedRole,
          speakerHomeX,
          sectionPulse,
          dragging: isDragging,
          reduce: !!reduce,
        })
        // While dragging, freeze at pre-drag visual spot so choreo clear doesn't jump
        const base = isDragging && dragBase[role] ? dragBase[role] : home
        const displayX = base.x + (isDragging ? 0 : c.ox)
        const displayY = base.y + (isDragging ? 0 : c.oy)
        const displayScale = isDragging ? 1 : c.scale
        const displayRot = isDragging ? 0 : c.rotateY

        return (
          <motion.div
            key={role}
            data-pet-actor={role}
            className="pointer-events-auto absolute touch-none"
            style={{ width: PET_W }}
            initial={false}
            animate={{
              x: displayX,
              y: displayY,
              scale: displayScale,
              rotateY: displayRot,
            }}
            transition={
              reduce || isDragging
                ? { duration: 0 }
                : { type: 'spring', stiffness: 140, damping: 18, mass: 0.7 }
            }
            drag={!reduce}
            dragMomentum={false}
            dragElastic={0.08}
            dragConstraints={layerRef}
            onPointerDown={() => {
              didDrag.current = false
              const pre = {
                x: home.x + c.ox,
                y: home.y + c.oy,
              }
              dragOrigin.current[role] = pre
              setDragBase((b) => ({ ...b, [role]: pre }))
              setDraggingRole(role)
            }}
            onDrag={(_, info) => {
              if (
                Math.abs(info.offset.x) > DRAG_CLICK_PX ||
                Math.abs(info.offset.y) > DRAG_CLICK_PX
              ) {
                didDrag.current = true
                setMenuRole(null)
              }
            }}
            onDragEnd={(_, info) => {
              const origin = dragOrigin.current[role] || home
              commitPos(role, origin.x + info.offset.x, origin.y + info.offset.y)
              setDraggingRole(null)
              setDragBase((b) => {
                const next = { ...b }
                delete next[role]
                return next
              })
            }}
            onPointerUp={() => {
              // Click without drag: release freeze
              if (!didDrag.current && draggingRole === role) {
                setDraggingRole(null)
                setDragBase((b) => {
                  const next = { ...b }
                  delete next[role]
                  return next
                })
              }
            }}
            onClick={() => {
              if (didDrag.current) return
              setMenuRole((cur) => (cur === role ? null : role))
            }}
            onDragOver={(e) => {
              if (dragSnack) e.preventDefault()
            }}
            onDrop={(e) => {
              e.preventDefault()
              if (e.dataTransfer.getData('text/pet-snack')) doFeed(role)
              setDragSnack(null)
            }}
          >
            <PetActor
              bare
              passive
              groundShadow
              def={def}
              state={state}
              bubble={bubble}
              label={labelFor(role)}
              size={72}
              walking={
                !reduce &&
                (state === 'speaking' || state === 'thinking' || sectionPulse)
              }
              className="cursor-grab active:cursor-grabbing"
            />
            {showMenu && (
              <div
                data-pet-menu
                className="absolute bottom-full left-1/2 z-40 mb-1 flex -translate-x-1/2 flex-col gap-0.5 rounded-lg border border-gray-200/80 bg-white/95 px-1 py-1 shadow-lg backdrop-blur-sm"
              >
                <button
                  type="button"
                  className="whitespace-nowrap rounded-md px-2 py-1 text-left text-[11px] text-gray-700 hover:bg-amber-50"
                  onClick={(e) => {
                    e.stopPropagation()
                    doPet(role)
                  }}
                >
                  {t('pet.action.pet')}
                </button>
                <button
                  type="button"
                  className="whitespace-nowrap rounded-md px-2 py-1 text-left text-[11px] text-gray-700 hover:bg-amber-50"
                  onClick={(e) => {
                    e.stopPropagation()
                    doFeed(role)
                  }}
                >
                  {t('pet.action.feed')}
                </button>
                <button
                  type="button"
                  className="whitespace-nowrap rounded-md px-2 py-1 text-left text-[11px] text-gray-700 hover:bg-brand-50"
                  onClick={(e) => {
                    e.stopPropagation()
                    setMenuRole(null)
                    onSelectRole?.(role)
                  }}
                >
                  {t('pet.action.locate')}
                </button>
              </div>
            )}
          </motion.div>
        )
      })}

      <div className="pointer-events-auto absolute bottom-3 right-3 z-40 flex flex-col items-end gap-1">
        <span className="rounded-md bg-white/80 px-1.5 py-0.5 text-[10px] text-gray-500 shadow-sm backdrop-blur-sm">
          {t('pet.snack_hint')}
        </span>
        <div className="flex gap-1 rounded-xl border border-gray-200/70 bg-white/90 p-1.5 shadow-md backdrop-blur-sm">
          {SNACKS.map((s) => (
            <button
              key={s.id}
              type="button"
              title={t(s.labelKey)}
              draggable={!reduce}
              className={clsx(
                'flex h-9 w-9 items-center justify-center rounded-lg text-lg transition hover:bg-amber-50',
                dragSnack === s.id && 'scale-110 bg-amber-50',
              )}
              onDragStart={(e) => {
                setDragSnack(s.id)
                e.dataTransfer.setData('text/pet-snack', s.id)
                e.dataTransfer.effectAllowed = 'copy'
              }}
              onDragEnd={(e) => {
                const role = hitTestPet(e.clientX, e.clientY)
                if (role) doFeed(role)
                setDragSnack(null)
              }}
              onClick={() => {
                const target =
                  speakingRole && visibleRoles.includes(speakingRole)
                    ? speakingRole
                    : visibleRoles[0]
                if (target) doFeed(target)
              }}
            >
              <span aria-hidden>{s.emoji}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
