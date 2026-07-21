import { create } from 'zustand'

interface PaymentState {
  open: boolean
  _resolver: ((ok: boolean) => void) | null
  /** 打开支付弹窗；返回 Promise，付款成功→true，取消→false。 */
  openGate: () => Promise<boolean>
  /** 关闭弹窗并回传结果（true=已付款/有额度，false=取消）。 */
  close: (ok: boolean) => void
}

export const usePaymentStore = create<PaymentState>((set, get) => ({
  open: false,
  _resolver: null,
  openGate: () =>
    new Promise<boolean>((resolve) => {
      // 若已有未决弹窗，先取消旧的
      const prev = get()._resolver
      if (prev) prev(false)
      set({ open: true, _resolver: resolve })
    }),
  close: (ok) => {
    const r = get()._resolver
    set({ open: false, _resolver: null })
    if (r) r(ok)
  },
}))
