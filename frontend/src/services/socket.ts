import { io, Socket } from 'socket.io-client'

let socket: Socket | null = null

export function getSocket(): Socket {
  if (!socket) {
    socket = io('/', {
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
