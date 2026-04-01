import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Locale = 'zh-CN' | 'zh-TW' | 'en'

export const REGION_LOCALE_MAP: Record<string, Locale> = {
  mainland: 'zh-CN',
  macau: 'zh-TW',
  hongkong: 'zh-TW',
  taiwan: 'zh-TW',
  international: 'en',
}

export const LOCALE_FONT: Record<Locale, string> = {
  'zh-CN': '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  'zh-TW': '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif',
  en: '"Inter", "Helvetica Neue", Arial, sans-serif',
}

interface LanguageState {
  locale: Locale
  setLocale: (l: Locale) => void
  setFromRegion: (region: string) => void
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set) => ({
      locale: 'zh-CN',
      setLocale: (locale) => {
        set({ locale })
        document.documentElement.style.fontFamily = LOCALE_FONT[locale]
      },
      setFromRegion: (region) => {
        const locale = REGION_LOCALE_MAP[region] || 'zh-CN'
        set({ locale })
        document.documentElement.style.fontFamily = LOCALE_FONT[locale]
      },
    }),
    { name: 'edu-language' },
  ),
)
