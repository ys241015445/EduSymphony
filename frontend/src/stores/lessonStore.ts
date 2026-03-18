import { create } from 'zustand'
import { api } from '../services/api'

export interface LessonSummary {
  id: string
  title: string
  subject: string
  grade_level: string
  status: string
  progress: number
  teaching_model_id: string
  created_at: string
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
  currentLesson: LessonDetail | null
  discussions: Discussion[]
  loading: boolean
  fetchLessons: () => Promise<void>
  fetchLesson: (id: string) => Promise<void>
  fetchDiscussions: (id: string) => Promise<void>
  createLesson: (form: FormData) => Promise<string>
  deleteLesson: (id: string) => Promise<void>
  regenerateStage: (lessonId: string, stageKey: string, version: string) => Promise<void>
  regenerateDiscussion: (lessonId: string, discussionId: string) => Promise<void>
}

export const useLessonStore = create<LessonState>()((set) => ({
  lessons: [],
  currentLesson: null,
  discussions: [],
  loading: false,

  fetchLessons: async () => {
    set({ loading: true })
    try {
      const res = await api.get('/api/v1/lessons')
      set({ lessons: res.data })
    } finally {
      set({ loading: false })
    }
  },

  fetchLesson: async (id) => {
    const res = await api.get(`/api/v1/lessons/${id}`)
    set({ currentLesson: res.data })
  },

  fetchDiscussions: async (id) => {
    const res = await api.get(`/api/v1/lessons/${id}/discussions`)
    set({ discussions: res.data })
  },

  createLesson: async (form) => {
    const res = await api.post('/api/v1/lessons', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data.id
  },

  deleteLesson: async (id) => {
    await api.delete(`/api/v1/lessons/${id}`)
    set((s) => ({ lessons: s.lessons.filter((l) => l.id !== id) }))
  },

  regenerateStage: async (lessonId, stageKey, version) => {
    await api.post(`/api/v1/lessons/${lessonId}/stages/${stageKey}/regenerate`, null, {
      params: { version },
    })
    const res = await api.get(`/api/v1/lessons/${lessonId}`)
    set({ currentLesson: res.data })
  },

  regenerateDiscussion: async (lessonId, discussionId) => {
    await api.post(`/api/v1/lessons/${lessonId}/discussions/${discussionId}/regenerate`)
    const res = await api.get(`/api/v1/lessons/${lessonId}/discussions`)
    set({ discussions: res.data })
  },
}))
