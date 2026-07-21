import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

/** Default API timeout (ms). */
export const API_TIMEOUT_MS = 60000

/** Zhuke recover/generate can run longer; list/history should stay fast after backend fix. */
export const ZHUKE_API_TIMEOUT_MS = 180000

/** Fast timeout for history list / light status polls — fail fast instead of 3 min spinner. */
export const ZHUKE_LIST_TIMEOUT_MS = 30000

/** Zhuke write ops (generate, parse, recover) — longer than default 60s. */
export const ZHUKE_WRITE_TIMEOUT_MS = 120000

export const api = axios.create({
  baseURL: '',
  timeout: API_TIMEOUT_MS,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    // 402 = 导出额度不足：自动弹支付窗（/payments/* 自行处理，避免重复弹窗）
    if (err.response?.status === 402) {
      const url: string = err.config?.url || ''
      if (!url.includes('/payments/')) {
        import('../stores/paymentStore')
          .then((m) => { void m.usePaymentStore.getState().openGate() })
          .catch(() => {})
      }
    }
    return Promise.reject(err)
  },
)
