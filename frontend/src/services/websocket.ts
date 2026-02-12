/**
 * WebSocket服务
 */
import { io, Socket } from 'socket.io-client';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

class WebSocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();

  connect(lessonId: string) {
    if (this.socket?.connected) {
      return;
    }

    this.socket = io(WS_URL, {
      transports: ['websocket'],
      query: {
        lesson_id: lessonId,
      },
    });

    this.socket.on('connect', () => {
      console.log('✅ WebSocket connected');
    });

    this.socket.on('disconnect', () => {
      console.log('❌ WebSocket disconnected');
    });

    // 监听进度更新
    this.socket.on('progress_update', (data) => {
      this.emit('progress', data);
    });

    // 监听讨论更新
    this.socket.on('discussion_update', (data) => {
      this.emit('discussion', data);
    });

    // 监听完成事件
    this.socket.on('lesson_completed', (data) => {
      this.emit('completed', data);
    });

    // 监听错误事件
    this.socket.on('lesson_error', (data) => {
      this.emit('error', data);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.listeners.clear();
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: Function) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)!.delete(callback);
    }
  }

  private emit(event: string, data: any) {
    if (this.listeners.has(event)) {
      this.listeners.get(event)!.forEach((callback) => {
        callback(data);
      });
    }
  }
}

export const wsService = new WebSocketService();

