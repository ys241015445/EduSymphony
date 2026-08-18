import type { PetSpecies } from './petRegistry'

interface Props {
  species: PetSpecies
  primary: string
  secondary: string
  accent: string
  mouthOpen?: boolean
  size?: number
  className?: string
}

/** Lightweight layered SVG pets — mouth swaps when speaking. */
export default function SvgPet({
  species,
  primary,
  secondary,
  accent,
  mouthOpen = false,
  size = 56,
  className,
}: Props) {
  const mouth = mouthOpen ? (
    <ellipse cx="32" cy="42" rx="5" ry="3.5" fill={accent} opacity="0.85" />
  ) : (
    <path d="M27 42 Q32 45 37 42" stroke={accent} strokeWidth="1.6" fill="none" strokeLinecap="round" />
  )

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      aria-hidden
    >
      {species === 'owl' && (
        <>
          <ellipse cx="32" cy="38" rx="18" ry="16" fill={primary} />
          <circle cx="32" cy="24" r="14" fill={primary} />
          <circle cx="25" cy="23" r="6" fill={secondary} />
          <circle cx="39" cy="23" r="6" fill={secondary} />
          <circle cx="25" cy="23" r="2.5" fill={accent} />
          <circle cx="39" cy="23" r="2.5" fill={accent} />
          <polygon points="32,28 28,34 36,34" fill={accent} />
          {mouth}
          <path d="M18 16 L22 22 M46 16 L42 22" stroke={accent} strokeWidth="2" strokeLinecap="round" />
        </>
      )}
      {species === 'fox' && (
        <>
          <ellipse cx="32" cy="40" rx="16" ry="14" fill={primary} />
          <circle cx="32" cy="26" r="12" fill={primary} />
          <polygon points="18,14 22,26 28,20" fill={primary} />
          <polygon points="46,14 42,26 36,20" fill={primary} />
          <polygon points="20,16 22,24 26,20" fill={secondary} />
          <polygon points="44,16 42,24 38,20" fill={secondary} />
          <circle cx="27" cy="26" r="2" fill={accent} />
          <circle cx="37" cy="26" r="2" fill={accent} />
          <ellipse cx="32" cy="32" rx="3" ry="2" fill={secondary} />
          {mouth}
          <path d="M44 44 Q52 38 54 46 Q48 48 44 44" fill={primary} />
        </>
      )}
      {species === 'rabbit' && (
        <>
          <ellipse cx="32" cy="42" rx="15" ry="13" fill={primary} />
          <circle cx="32" cy="30" r="11" fill={primary} />
          <ellipse cx="24" cy="12" rx="4" ry="12" fill={primary} />
          <ellipse cx="40" cy="12" rx="4" ry="12" fill={primary} />
          <ellipse cx="24" cy="12" rx="2" ry="8" fill={secondary} />
          <ellipse cx="40" cy="12" rx="2" ry="8" fill={secondary} />
          <circle cx="28" cy="29" r="2" fill={accent} />
          <circle cx="36" cy="29" r="2" fill={accent} />
          <ellipse cx="32" cy="34" rx="2.5" ry="1.8" fill={secondary} />
          {mouth}
        </>
      )}
      {species === 'dolphin' && (
        <>
          <ellipse cx="34" cy="34" rx="18" ry="12" fill={primary} />
          <path d="M16 34 Q10 28 8 34 Q10 40 16 34" fill={primary} />
          <path d="M48 24 L54 16 L50 28 Z" fill={accent} />
          <circle cx="42" cy="30" r="2.2" fill={accent} />
          <path d="M40 36 Q44 38 46 36" stroke={accent} strokeWidth="1.4" fill="none" strokeLinecap="round" />
          {mouthOpen ? (
            <ellipse cx="46" cy="36" rx="3" ry="2" fill={accent} opacity="0.7" />
          ) : null}
          <ellipse cx="28" cy="40" rx="5" ry="2.5" fill={secondary} opacity="0.6" />
        </>
      )}
      {species === 'cat' && (
        <>
          <ellipse cx="32" cy="40" rx="15" ry="13" fill={primary} />
          <circle cx="32" cy="28" r="12" fill={primary} />
          <polygon points="20,14 24,26 30,20" fill={primary} />
          <polygon points="44,14 40,26 34,20" fill={primary} />
          <circle cx="27" cy="28" r="2" fill={accent} />
          <circle cx="37" cy="28" r="2" fill={accent} />
          <path d="M32 31 L32 35" stroke={accent} strokeWidth="1.2" />
          <path d="M26 32 Q22 34 20 30 M38 32 Q42 34 44 30" stroke={secondary} strokeWidth="1.2" fill="none" />
          {mouth}
        </>
      )}
      {species === 'bear' && (
        <>
          <ellipse cx="32" cy="38" rx="17" ry="15" fill={primary} />
          <circle cx="32" cy="26" r="13" fill={primary} />
          <circle cx="18" cy="16" r="5" fill={primary} />
          <circle cx="46" cy="16" r="5" fill={primary} />
          <circle cx="18" cy="16" r="2.5" fill={secondary} />
          <circle cx="46" cy="16" r="2.5" fill={secondary} />
          <circle cx="27" cy="26" r="2" fill={accent} />
          <circle cx="37" cy="26" r="2" fill={accent} />
          <ellipse cx="32" cy="32" rx="5" ry="4" fill={secondary} />
          {mouth}
        </>
      )}
      {species === 'deer' && (
        <>
          <ellipse cx="32" cy="42" rx="14" ry="12" fill={primary} />
          <circle cx="32" cy="28" r="11" fill={primary} />
          <path d="M24 10 L22 4 M24 10 L26 4 M40 10 L38 4 M40 10 L42 4" stroke={accent} strokeWidth="1.8" strokeLinecap="round" />
          <path d="M24 16 L24 10 M40 16 L40 10" stroke={accent} strokeWidth="1.8" />
          <circle cx="28" cy="28" r="2" fill={accent} />
          <circle cx="36" cy="28" r="2" fill={accent} />
          <ellipse cx="32" cy="33" rx="2.5" ry="1.8" fill={secondary} />
          {mouth}
        </>
      )}
    </svg>
  )
}
