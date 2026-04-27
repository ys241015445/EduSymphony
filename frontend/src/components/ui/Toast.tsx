import { useEffect } from 'react'
import { create } from 'zustand'
import { CheckCircle2, AlertTriangle, Info, X, Loader2 } from 'lucide-react'

export type ToastKind = 'success' | 'error' | 'info' | 'loading'

export interface ToastItem {
  id: string
  kind: ToastKind
  message: string
  duration?: number
}

interface ToastState {
  items: ToastItem[]
  push: (item: Omit<ToastItem, 'id'>) => string
  dismiss: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  items: [],
  push: (t) => {
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    set((s) => ({ items: [...s.items, { id, duration: 4000, ...t }] }))
    return id
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
}))

export const toast = {
  success: (msg: string, duration?: number) =>
    useToastStore.getState().push({ kind: 'success', message: msg, duration }),
  error: (msg: string, duration?: number) =>
    useToastStore.getState().push({ kind: 'error', message: msg, duration: duration ?? 6000 }),
  info: (msg: string, duration?: number) =>
    useToastStore.getState().push({ kind: 'info', message: msg, duration }),
  loading: (msg: string) =>
    useToastStore.getState().push({ kind: 'loading', message: msg, duration: 0 }),
  dismiss: (id: string) => useToastStore.getState().dismiss(id),
}

const ICONS: Record<ToastKind, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
  loading: Loader2,
}

const COLORS: Record<ToastKind, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  loading: 'bg-gray-50 border-gray-200 text-gray-700',
}

function ToastCard({ item }: { item: ToastItem }) {
  const { dismiss } = useToastStore()
  const Icon = ICONS[item.kind]

  useEffect(() => {
    if (!item.duration || item.duration <= 0) return
    const t = setTimeout(() => dismiss(item.id), item.duration)
    return () => clearTimeout(t)
  }, [item.id, item.duration, dismiss])

  return (
    <div
      className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 shadow-sm w-80 ${COLORS[item.kind]}`}
    >
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${item.kind === 'loading' ? 'animate-spin' : ''}`} />
      <div className="flex-1 text-sm leading-relaxed">{item.message}</div>
      <button
        onClick={() => dismiss(item.id)}
        className="text-current opacity-50 hover:opacity-100 transition"
        aria-label="close"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function Toaster() {
  const items = useToastStore((s) => s.items)
  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-auto">
      {items.map((i) => (
        <ToastCard key={i.id} item={i} />
      ))}
    </div>
  )
}
