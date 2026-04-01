import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../services/api'

interface User {
  id: string
  username: string
  email: string
  role: string
  quota_remaining: number
}

interface AuthState {
  token: string | null
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,

      login: async (email, password) => {
        const res = await api.post('/api/v1/auth/login', { email, password })
        set({ token: res.data.access_token, user: res.data.user })
      },

      register: async (username, email, password) => {
        const res = await api.post('/api/v1/auth/register', { username, email, password })
        set({ token: res.data.access_token, user: res.data.user })
      },

      logout: () => {
        set({ token: null, user: null })
      },

      fetchMe: async () => {
        try {
          const res = await api.get('/api/v1/auth/me')
          set({ user: res.data })
        } catch {
          set({ token: null, user: null })
        }
      },
    }),
    { name: 'edusymphony-auth' },
  ),
)
