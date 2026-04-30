import { create } from 'zustand'
import { api } from '../services/api'

/** Optional admin scope when viewing another user's lessons. */
export type LessonsScope = { for_user_id?: string }

export const scopeParams = (scope?: LessonsScope) =>
  scope?.for_user_id ? { for_user_id: scope.for_user_id } : undefined

export interface LessonSummary {
  id: string
  title: string
  subject: string
  grade_level: string
  status: string
  progress: number
  teaching_model_id: string
  created_at: string
  mode?: string
  has_full_optimized?: boolean
  has_stages?: boolean
}

/** GET /api/v1/series 列表项（与后端 SeriesListResponse 对齐） */
export interface SeriesSummary {
  id: string
  title: string
  subject: string
  grade_level: string
  total_weeks: number
  lessons_per_week: number
  status: string
  education_level?: string
  created_at?: string | null
}

export interface LessonDetail {
  id: string
  user_id: string
  title: string
  subject: string
  grade_level: string
  specific_grade?: string
  region: string
  teaching_model_id?: string
  topic?: string
  avoid_issues?: string
  student_type?: string
  status: string
  progress: number
  current_stage: number
  error_message?: string
  source_type: string
  parsed_content?: string
  final_content?: any
  mode?: string
  started_at?: string
  completed_at?: string
  created_at?: string
}

export interface Discussion {
  id: string
  lesson_plan_id: string
  stage: number
  round: number
  topic?: string
  agent_role: string
  opinion: string
  votes?: any
  pass_rate?: number
  is_accepted: boolean
  created_at?: string
}

interface LessonState {
  lessons: LessonSummary[]
  seriesList: SeriesSummary[]
  currentLesson: LessonDetail | null
  discussions: Discussion[]
  loading: boolean
  loadingSeries: boolean
  fetchLessons: (scope?: LessonsScope) => Promise<void>
  fetchSeries: (scope?: LessonsScope) => Promise<void>
  fetchLesson: (id: string, scope?: LessonsScope) => Promise<void>
  fetchDiscussions: (id: string, scope?: LessonsScope) => Promise<void>
  createLesson: (form: FormData, scope?: LessonsScope) => Promise<string>
  deleteLesson: (id: string, scope?: LessonsScope) => Promise<void>
  regenerateStage: (lessonId: string, stageKey: string, version: string, scope?: LessonsScope) => Promise<void>
  regenerateDiscussion: (lessonId: string, discussionId: string, scope?: LessonsScope) => Promise<void>
  regenerateOptimized: (lessonId: string, scope?: LessonsScope) => Promise<void>
  extendQuickLesson: (lessonId: string, scope?: LessonsScope) => Promise<void>
}

export const useLessonStore = create<LessonState>()((set) => ({
  lessons: [],
  seriesList: [],
  currentLesson: null,
  discussions: [],
  loading: false,
  loadingSeries: false,

  fetchLessons: async (scope) => {
    set({ loading: true })
    try {
      const res = await api.get('/api/v1/lessons', { params: scopeParams(scope) })
      set({ lessons: res.data })
    } finally {
      set({ loading: false })
    }
  },

  fetchSeries: async (scope) => {
    set({ loadingSeries: true })
    try {
      const res = await api.get('/api/v1/series', { params: scopeParams(scope) })
      set({ seriesList: res.data })
    } finally {
      set({ loadingSeries: false })
    }
  },

  fetchLesson: async (id, scope) => {
    const res = await api.get(`/api/v1/lessons/${id}`, { params: scopeParams(scope) })
    set({ currentLesson: res.data })
  },

  fetchDiscussions: async (id, scope) => {
    const res = await api.get(`/api/v1/lessons/${id}/discussions`, { params: scopeParams(scope) })
    set({ discussions: res.data })
  },

  createLesson: async (form, scope) => {
    const res = await api.post('/api/v1/lessons', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: scopeParams(scope),
    })
    return res.data.id
  },

  deleteLesson: async (id, scope) => {
    await api.delete(`/api/v1/lessons/${id}`, { params: scopeParams(scope) })
    set((s) => ({ lessons: s.lessons.filter((l) => l.id !== id) }))
  },

  regenerateStage: async (lessonId, stageKey, version, scope) => {
    await api.post(`/api/v1/lessons/${lessonId}/stages/${stageKey}/regenerate`, null, {
      params: { version, ...(scopeParams(scope) ?? {}) },
    })
    const res = await api.get(`/api/v1/lessons/${lessonId}`, { params: scopeParams(scope) })
    set({ currentLesson: res.data })
  },

  regenerateDiscussion: async (lessonId, discussionId, scope) => {
    await api.post(`/api/v1/lessons/${lessonId}/discussions/${discussionId}/regenerate`, null, {
      params: scopeParams(scope),
    })
    const res = await api.get(`/api/v1/lessons/${lessonId}/discussions`, { params: scopeParams(scope) })
    set({ discussions: res.data })
  },

  regenerateOptimized: async (lessonId, scope) => {
    await api.post(`/api/v1/lessons/${lessonId}/regenerate-optimized`, null, {
      params: scopeParams(scope),
    })
  },

  extendQuickLesson: async (lessonId, scope) => {
    await api.post(`/api/v1/lessons/${lessonId}/regenerate-draft`, null, {
      params: scopeParams(scope),
    })
  },
}))
