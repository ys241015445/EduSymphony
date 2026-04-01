import { create } from 'zustand'
import { api } from '../services/api'

interface MaterialGenStore {
  startingKeys: Set<string>

  startGeneration: (
    lessonId: string,
    contentVersion: 'draft' | 'optimized',
  ) => Promise<void>
}

function taskKey(lessonId: string, contentVersion: string) {
  return `${lessonId}_${contentVersion}`
}

export const useMaterialGenStore = create<MaterialGenStore>((set, get) => ({
  startingKeys: new Set(),

  startGeneration: async (lessonId, contentVersion) => {
    const key = taskKey(lessonId, contentVersion)
    if (get().startingKeys.has(key)) return

    set((s) => ({ startingKeys: new Set(s.startingKeys).add(key) }))
    try {
      const formData = new FormData()
      formData.append('content_version', contentVersion)
      await api.post(`/api/v1/export/material/generate/${lessonId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    } finally {
      set((s) => {
        const next = new Set(s.startingKeys)
        next.delete(key)
        return { startingKeys: next }
      })
    }
  },
}))
