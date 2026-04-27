import { create } from 'zustand'
import { api } from '../services/api'
import { getSocket, joinUser } from '../services/socket'
import { toast } from '../components/ui/Toast'
import { useAuthStore } from './authStore'

export type ToolType = 'outline' | 'ppt' | 'exercises' | 'practice'

export interface JobItem {
  result_id: string
  tool_type: ToolType
  title: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  error?: string
  enqueued_at: number
}

interface JobsState {
  items: JobItem[]
  initialized: boolean
  _socketBound: boolean
  add: (j: Omit<JobItem, 'status' | 'enqueued_at'> & { status?: JobItem['status'] }) => void
  markCompleted: (result_id: string, extra?: { title?: string }) => void
  markFailed: (result_id: string, err?: string) => void
  remove: (result_id: string) => void
  refreshFromServer: () => Promise<void>
  bindSocket: () => void
  reset: () => void
}

const KIND_TO_TOOL: Record<string, ToolType | undefined> = {
  tool_outline: 'outline',
  tool_ppt: 'ppt',
  tool_exercises: 'exercises',
  tool_practice: 'practice',
}

export const useJobsStore = create<JobsState>((set, get) => ({
  items: [],
  initialized: false,
  _socketBound: false,

  add: (j) => {
    const existing = get().items.find((i) => i.result_id === j.result_id)
    const next: JobItem = {
      result_id: j.result_id,
      tool_type: j.tool_type,
      title: j.title || '',
      status: j.status || 'queued',
      enqueued_at: Date.now(),
    }
    if (existing) {
      set({ items: get().items.map((i) => (i.result_id === j.result_id ? { ...i, ...next } : i)) })
    } else {
      set({ items: [next, ...get().items] })
    }
  },

  markCompleted: (result_id, extra) => {
    set({
      items: get().items.map((i) =>
        i.result_id === result_id ? { ...i, status: 'completed', ...(extra?.title ? { title: extra.title } : {}) } : i,
      ),
    })
    setTimeout(() => {
      set({ items: get().items.filter((i) => i.result_id !== result_id) })
    }, 4000)
  },

  markFailed: (result_id, err) => {
    set({
      items: get().items.map((i) =>
        i.result_id === result_id ? { ...i, status: 'failed', error: err || '' } : i,
      ),
    })
  },

  remove: (result_id) => {
    set({ items: get().items.filter((i) => i.result_id !== result_id) })
  },

  refreshFromServer: async () => {
    try {
      const kinds = 'tool_outline,tool_ppt,tool_exercises,tool_practice'
      const [queued, running] = await Promise.all([
        api.get('/api/v1/system/queue/jobs', { params: { mine: true, status: 'queued', kinds, limit: 100 } }),
        api.get('/api/v1/system/queue/jobs', { params: { mine: true, status: 'running', kinds, limit: 100 } }),
      ])
      const rows: any[] = [...(queued.data?.jobs || []), ...(running.data?.jobs || [])]
      const mapped: JobItem[] = []
      for (const r of rows) {
        const tt = KIND_TO_TOOL[r.kind]
        if (!tt) continue
        mapped.push({
          result_id: r.target_id,
          tool_type: tt,
          title: '',
          status: r.status === 'running' ? 'running' : 'queued',
          enqueued_at: r.created_at ? Date.parse(r.created_at) || Date.now() : Date.now(),
        })
      }
      // Try to hydrate titles from CourseToolResult (best-effort, one call per row is fine for small list)
      await Promise.all(
        mapped.map(async (it) => {
          try {
            const r = await api.get(`/api/v1/course-tools/results/${it.result_id}`)
            it.title = (r.data?.title as string) || ''
          } catch {}
        }),
      )
      set({ items: mapped, initialized: true })
    } catch {
      set({ initialized: true })
    }
  },

  bindSocket: () => {
    if (get()._socketBound) return
    const s = getSocket()
    const user = useAuthStore.getState().user
    if (user?.id) joinUser(user.id)

    s.on('course_tool_completed', (payload: any) => {
      if (!payload?.result_id) return
      get().markCompleted(payload.result_id, { title: payload.title })
      const tt = payload.tool_type || ''
      toast.success(
        payload.title ? `已生成：${payload.title}` : `${toolTypeLabel(tt)}生成完成`,
      )
    })
    s.on('course_tool_failed', (payload: any) => {
      if (!payload?.result_id) return
      get().markFailed(payload.result_id, payload?.error)
      toast.error(payload?.error ? `生成失败：${payload.error}` : '任务生成失败')
    })
    set({ _socketBound: true })
  },

  reset: () => set({ items: [], initialized: false }),
}))

function toolTypeLabel(t: string): string {
  switch (t) {
    case 'outline':
      return '内容大纲'
    case 'ppt':
      return 'PPT'
    case 'exercises':
      return '习题作业'
    case 'practice':
      return '课上练习'
    default:
      return '任务'
  }
}
