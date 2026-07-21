import { io, Socket } from 'socket.io-client'
import { useAuthStore } from '../stores/authStore'

let socket: Socket | null = null

function socketAuthPayload(): { token?: string } {
  const token = useAuthStore.getState().token
  return token ? { token } : {}
}

function socketBaseURL(): string {
  const fromEnv = (import.meta.env.VITE_SOCKET_ORIGIN as string | undefined)?.trim()
  if (fromEnv) return fromEnv.replace(/\/$/, '')
  // Dev: same origin as Vite (3000) — /socket.io is proxied to uvicorn with ws:true.
  if (import.meta.env.DEV) return window.location.origin
  return window.location.origin
}

export function getSocket(): Socket {
  if (!socket) {
    socket = io(socketBaseURL(), {
      path: '/socket.io/',
      transports: ['websocket', 'polling'],
      autoConnect: true,
      auth: socketAuthPayload(),
    })
  }
  return socket
}

export function joinLesson(lessonId: string) {
  const s = getSocket()
  s.emit('join_lesson', { lesson_id: lessonId })
}

export function leaveLesson(lessonId: string) {
  const s = getSocket()
  s.emit('leave_lesson', { lesson_id: lessonId })
}

export function joinUser(userId: string) {
  const s = getSocket()
  const doJoin = () => s.emit('join_user', { user_id: userId })
  if (s.connected) doJoin()
  s.on('connect', doJoin)
}

export function leaveUser(userId: string) {
  const s = getSocket()
  s.emit('leave_user', { user_id: userId })
}
