import { create } from 'zustand'
import { api } from '../services/api'

export interface DocumentSummary {
  lesson_plan_id?: string | null
  source_kind: string
  source_ref_id?: string | null
  title: string
  latest_version_id: string
  latest_version_number: number
  version_count: number
  updated_at?: string | null
  is_virtual?: boolean
  lesson_status?: string | null
  lesson_mode?: string | null
  series_id?: string | null
  deleted_at?: string | null
}

export interface DocumentVersionBrief {
  id: string
  title: string
  version_number: number
  change_source: string
  change_summary?: string | null
  is_current: boolean
  created_at?: string | null
}

export interface DocumentVersionFull extends DocumentVersionBrief {
  user_id: string
  lesson_plan_id?: string | null
  source_kind: string
  source_ref_id?: string | null
  content_markdown: string
  parent_version_id?: string | null
  ai_prompt?: string | null
}

export interface ExportRecordItem {
  id: string
  user_id: string
  lesson_plan_id?: string | null
  version_id?: string | null
  source_kind: string
  format: string
  file_name: string
  file_size?: number | null
  file_path?: string | null
  job_id?: string | null
  status?: string | null
  error_message?: string | null
  // JSON blob with kind-specific context. For source_kind='zhuke_generation'
  // it carries `{ result_id, course_name, lessons_count, failures_count, ... }`
  // — the UI uses `result_id` (or job_id as a fallback) to call the
  // /semester-helper/zhuke/{rid}/download endpoint instead of the generic one.
  params?: Record<string, any> | null
  expires_at?: string | null
  created_at?: string | null
  deleted_at?: string | null
  is_available: boolean
}

export type DocumentsScope = { for_user_id?: string; include_deleted?: boolean }

interface DocumentsState {
  library: DocumentSummary[]
  versions: DocumentVersionBrief[]
  current: DocumentVersionFull | null
  exports: ExportRecordItem[]
  loadingLib: boolean
  loadingVer: boolean
  loadingExports: boolean

  fetchLibrary: (params?: { series_id?: string; include_virtual?: boolean; for_user_id?: string; include_deleted?: boolean }) => Promise<void>
  ensureVersion: (lessonId: string, sourceKind?: string, scope?: DocumentsScope) => Promise<{ version_id: string; title: string; source_kind: string; is_new: boolean }>
  fetchVersionsForLesson: (lessonId: string, sourceKind?: string, scope?: DocumentsScope) => Promise<void>
  fetchVersion: (versionId: string) => Promise<DocumentVersionFull>
  createVersion: (
    body: {
      lesson_plan_id?: string | null
      source_kind?: string
      source_ref_id?: string | null
      title?: string
      content_markdown: string
      parent_version_id?: string | null
      change_summary?: string | null
      change_source?: 'user_edit' | 'ai_full' | 'ai_paragraph'
      ai_prompt?: string | null
    },
    scope?: DocumentsScope,
  ) => Promise<DocumentVersionFull>
  deleteVersion: (versionId: string) => Promise<void>
  setCurrentVersion: (versionId: string) => Promise<DocumentVersionFull>

  fetchExports: (scope?: DocumentsScope) => Promise<void>
  deleteExport: (recordId: string) => Promise<void>
}

export const useDocumentsStore = create<DocumentsState>()((set) => ({
  library: [],
  versions: [],
  current: null,
  exports: [],
  loadingLib: false,
  loadingVer: false,
  loadingExports: false,

  fetchLibrary: async (params) => {
    set({ loadingLib: true })
    try {
      const res = await api.get('/api/v1/documents/library', {
        params: {
          ...(params?.series_id ? { series_id: params.series_id } : {}),
          ...(params?.include_virtual !== undefined ? { include_virtual: params.include_virtual } : {}),
          ...(params?.for_user_id ? { for_user_id: params.for_user_id } : {}),
          ...(params?.include_deleted ? { include_deleted: true } : {}),
        },
      })
      set({ library: res.data })
    } finally {
      set({ loadingLib: false })
    }
  },

  ensureVersion: async (lessonId, sourceKind = 'lesson_optimized', scope) => {
    const res = await api.post(
      `/api/v1/documents/lesson/${lessonId}/ensure-version`,
      null,
      {
        params: {
          source_kind: sourceKind,
          ...(scope?.for_user_id ? { for_user_id: scope.for_user_id } : {}),
        },
      },
    )
    return res.data
  },

  fetchVersionsForLesson: async (lessonId, sourceKind = 'lesson_optimized', scope) => {
    set({ loadingVer: true })
    try {
      const res = await api.get(`/api/v1/documents/lesson/${lessonId}/versions`, {
        params: {
          source_kind: sourceKind,
          ...(scope?.for_user_id ? { for_user_id: scope.for_user_id } : {}),
        },
      })
      set({ versions: res.data })
    } finally {
      set({ loadingVer: false })
    }
  },

  fetchVersion: async (versionId) => {
    const res = await api.get(`/api/v1/documents/versions/${versionId}`)
    set({ current: res.data })
    return res.data as DocumentVersionFull
  },

  createVersion: async (body, scope) => {
    const res = await api.post('/api/v1/documents/versions', body, {
      params: scope?.for_user_id ? { for_user_id: scope.for_user_id } : undefined,
    })
    set({ current: res.data })
    return res.data as DocumentVersionFull
  },

  deleteVersion: async (versionId) => {
    await api.delete(`/api/v1/documents/versions/${versionId}`)
    set((s) => ({ versions: s.versions.filter((v) => v.id !== versionId) }))
  },

  setCurrentVersion: async (versionId) => {
    const res = await api.post(`/api/v1/documents/versions/${versionId}/set-current`)
    set({ current: res.data })
    return res.data as DocumentVersionFull
  },

  fetchExports: async (scope) => {
    set({ loadingExports: true })
    try {
      const res = await api.get('/api/v1/documents/exports', {
        params: {
          limit: 200,
          ...(scope?.for_user_id ? { for_user_id: scope.for_user_id } : {}),
          ...(scope?.include_deleted ? { include_deleted: true } : {}),
        },
      })
      set({ exports: res.data })
    } finally {
      set({ loadingExports: false })
    }
  },

  deleteExport: async (recordId) => {
    await api.delete(`/api/v1/documents/exports/${recordId}`)
    set((s) => ({ exports: s.exports.filter((e) => e.id !== recordId) }))
  },
}))
