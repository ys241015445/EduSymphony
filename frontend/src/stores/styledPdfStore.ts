import { create } from 'zustand'
import { api } from '../services/api'

interface StyledPdfStore {
  starting: boolean
  error: string | null

  startGeneration: (
    lessonId: string,
    templateType: 'default' | 'upload',
    contentVersion: string,
    templateFile: File | null,
  ) => Promise<void>
  clearError: () => void
}

export const useStyledPdfStore = create<StyledPdfStore>((set, get) => ({
  starting: false,
  error: null,

  startGeneration: async (lessonId, templateType, contentVersion, templateFile) => {
    if (get().starting) return

    set({ starting: true, error: null })
    try {
      const formData = new FormData()
      formData.append('template_type', templateType)
      formData.append('content_version', contentVersion)
      if (templateType === 'upload' && templateFile) {
        formData.append('template_file', templateFile)
      }
      await api.post(`/api/v1/export/styled-pdf/generate/${lessonId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    } catch (e: any) {
      const detail = e.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d?.msg || String(d)).join('; ') : e.message || 'Generation request failed'
      set({ error: msg })
      throw e
    } finally {
      set({ starting: false })
    }
  },

  clearError: () => set({ error: null }),
}))
