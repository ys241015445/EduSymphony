import { create } from 'zustand'
import { api } from '../services/api'

interface StyledPdfStore {
  starting: boolean

  startGeneration: (
    lessonId: string,
    templateType: 'default' | 'upload',
    contentVersion: string,
    templateFile: File | null,
  ) => Promise<void>
}

export const useStyledPdfStore = create<StyledPdfStore>((set, get) => ({
  starting: false,

  startGeneration: async (lessonId, templateType, contentVersion, templateFile) => {
    if (get().starting) return

    set({ starting: true })
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
    } finally {
      set({ starting: false })
    }
  },
}))
