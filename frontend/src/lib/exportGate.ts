import { api } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { usePaymentStore } from '../stores/paymentStore'
import { parseAccessLevel, isAdmin } from './access'

/** 当前用户是否免付费（管理员或白名单）。 */
export function isExportExempt(): boolean {
  const user = useAuthStore.getState().user
  if (!user) return false
  if (isAdmin(parseAccessLevel(user.access_level))) return true
  return !!user.export_pay_exempt
}

/** 剩余导出额度。 */
export function exportCredits(): number {
  return useAuthStore.getState().user?.export_credits ?? 0
}

/**
 * 服务端下载前调用：确保有额度/免付费，否则弹支付窗。
 * 返回 true 表示可继续下载（后端会在下载端点扣 1 额度）；false 表示用户取消。
 */
export async function ensureExportAllowed(): Promise<boolean> {
  if (isExportExempt() || exportCredits() > 0) return true
  return usePaymentStore.getState().openGate()
}

/** 下载完成后刷新用户额度显示（后端已扣额）。 */
export async function refreshCreditsSoon(): Promise<void> {
  try {
    await useAuthStore.getState().fetchMe()
  } catch {
    /* ignore */
  }
}

/**
 * 纯前端 blob 下载专用：先在服务端扣 1 额度（管理员/白名单为 no-op）。
 * 额度不足自动弹支付窗并在付款后重试；返回 true 表示可继续生成/下载。
 */
export async function consumeExportCredit(): Promise<boolean> {
  const doConsume = async (): Promise<'ok' | 'need_pay' | 'fail'> => {
    try {
      const res = await api.post('/api/v1/payments/consume')
      const u = useAuthStore.getState().user
      if (u && typeof res.data?.export_credits === 'number') {
        useAuthStore.setState({ user: { ...u, export_credits: res.data.export_credits } })
      }
      return 'ok'
    } catch (e: any) {
      if (e?.response?.status === 402) return 'need_pay'
      return 'fail'
    }
  }

  let r = await doConsume()
  if (r === 'ok') return true
  if (r === 'fail') return false
  // need_pay → 弹窗
  const paid = await usePaymentStore.getState().openGate()
  if (!paid) return false
  r = await doConsume()
  return r === 'ok'
}
