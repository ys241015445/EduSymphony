import { io, Socket } from 'socket.io-client'

let socket: Socket | null = null

function socketBaseURL(): string {
  const fromEnv = (import.meta.env.VITE_SOCKET_ORIGIN as string | undefined)?.trim()
  if (fromEnv) return fromEnv.replace(/\/$/, '')
  if (import.meta.env.DEV) {
    const port = (import.meta.env.VITE_DEV_BACKEND_PORT as string | undefined) || '3002'
    const { protocol, hostname } = window.location
    return `${protocol}//${hostname}:${port}`
  }
  return window.location.origin
}

export function getSocket(): Socket {
  if (!socket) {
    socket = io(socketBaseURL(), {
      path: '/socket.io/',
      transports: ['websocket', 'polling'],
      autoConnect: true,
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
