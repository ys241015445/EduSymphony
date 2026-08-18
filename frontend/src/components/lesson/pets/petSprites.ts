/** Optional Seedream sprite overlays under /public/pets/{spriteKey}/{pose}.png|.jpg|.webp */



import type { PetPose } from './petRegistry'



const KNOWN = new Set<string>()

const MISSING = new Set<string>()

const URL_CACHE = new Map<string, string>()



export function spriteUrl(spriteKey: string, pose: PetPose): string {

  return URL_CACHE.get(`${spriteKey}/${pose}`) || `/pets/${spriteKey}/${pose}.png`

}



function candidates(spriteKey: string, pose: PetPose): string[] {

  // Prefer matted transparent PNG; jpg/webp are opaque fallbacks

  return [

    `/pets/${spriteKey}/${pose}.png`,

    `/pets/${spriteKey}/${pose}.jpg`,

    `/pets/${spriteKey}/${pose}.webp`,

  ]

}



/** Probe once per key; cache hit/miss so we don't spam 404s. */

export function probeSprite(spriteKey: string, pose: PetPose): Promise<boolean> {

  const id = `${spriteKey}/${pose}`

  if (KNOWN.has(id)) return Promise.resolve(true)

  if (MISSING.has(id)) return Promise.resolve(false)



  const tryOne = (url: string) =>

    new Promise<boolean>((resolve) => {

      const img = new Image()

      img.onload = () => resolve(true)

      img.onerror = () => resolve(false)

      img.src = url

    })



  return (async () => {

    for (const url of candidates(spriteKey, pose)) {

      if (await tryOne(url)) {

        KNOWN.add(id)

        URL_CACHE.set(id, url)

        return true

      }

    }

    MISSING.add(id)

    return false

  })()

}



export function hasSpriteCached(spriteKey: string, pose: PetPose): boolean {

  return KNOWN.has(`${spriteKey}/${pose}`)

}


