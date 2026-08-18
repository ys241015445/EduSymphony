import { useEffect, useState } from 'react'
import { getPetDef } from './petRegistry'
import SvgPet from './SvgPet'
import { hasSpriteCached, probeSprite, spriteUrl } from './petSprites'

/** Tiny avatar for AgentCard — prefers idle sprite when present. */
export default function PetAvatar({ role, streaming, size = 26 }: { role: string; streaming?: boolean; size?: number }) {
  const pet = getPetDef(role)
  const [useSprite, setUseSprite] = useState(() =>
    pet ? hasSpriteCached(pet.spriteKey, 'idle') : false,
  )

  useEffect(() => {
    if (!pet) return
    let cancelled = false
    probeSprite(pet.spriteKey, 'idle').then((ok) => {
      if (!cancelled) setUseSprite(ok)
    })
    return () => { cancelled = true }
  }, [pet])

  if (!pet) {
    return <span className="text-[10px] font-bold text-gray-500">AI</span>
  }

  if (useSprite) {
    return (
      <img
        src={spriteUrl(pet.spriteKey, 'idle')}
        alt=""
        width={size}
        height={size}
        className={`object-contain ${streaming ? 'scale-110' : ''} transition-transform`}
        draggable={false}
      />
    )
  }

  return (
    <SvgPet
      species={pet.species}
      primary={pet.primary}
      secondary={pet.secondary}
      accent={pet.accent}
      size={size}
      mouthOpen={!!streaming}
    />
  )
}
