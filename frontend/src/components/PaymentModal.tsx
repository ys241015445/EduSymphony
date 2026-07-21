import { useEffect, useRef, useState } from 'react'
import QRCode from 'qrcode'
import { Loader2, X, CheckCircle2 } from 'lucide-react'
import { api } from '../services/api'
import { usePaymentStore } from '../stores/paymentStore'
import { useAuthStore } from '../stores/authStore'
import { toast } from './ui/Toast'

type PayType = 1 | 2 // 1=微信 2=支付宝

export default function PaymentModal() {
  const open = usePaymentStore((s) => s.open)
  const close = usePaymentStore((s) => s.close)

  const [payType, setPayType] = useState<PayType>(2)
  const [loading, setLoading] = useState(false)
  const [claiming, setClaiming] = useState(false)
  const [error, setError] = useState('')
  const [price, setPrice] = useState(5)
  const [tempCredits, setTempCredits] = useState(1)
  const [aliQr, setAliQr] = useState('')
  const [wxQr, setWxQr] = useState('')
  const [done, setDone] = useState(false)
  const genOnce = useRef(false)

  useEffect(() => {
    if (!open) { genOnce.current = false; return }
    setError(''); setDone(false)
    setLoading(true)
    api.get('/api/v1/payments/config')
      .then(async (r) => {
        setPrice(r.data?.price ?? 5)
        setTempCredits(r.data?.temp_credits ?? 1)
        const ali = r.data?.alipay_qr || ''
        const wx = r.data?.wechat_qr || ''
        try { if (ali) setAliQr(await QRCode.toDataURL(ali, { width: 220, margin: 1 })) } catch { /* noop */ }
        try { if (wx) setWxQr(await QRCode.toDataURL(wx, { width: 220, margin: 1 })) } catch { /* noop */ }
      })
      .catch(() => setError('无法加载支付信息'))
      .finally(() => setLoading(false))
  }, [open])

  const claim = async () => {
    setClaiming(true); setError('')
    try {
      const res = await api.post('/api/v1/payments/claim', { pay_type: payType })
      const u = useAuthStore.getState().user
      if (u && typeof res.data?.export_credits === 'number') {
        useAuthStore.setState({ user: { ...u, export_credits: res.data.export_credits } })
      }
      setDone(true)
      toast.success(`已发放 ${res.data?.temp_credits ?? tempCredits} 次临时额度，管理员核对到账后补足`)
      window.setTimeout(() => close(true), 1000)
    } catch (e: any) {
      const code = e?.response?.status
      if (code === 429) setError(e?.response?.data?.detail || '你已有一笔待核对的充值，请等管理员确认')
      else setError(e?.response?.data?.detail || '提交失败，请重试')
    } finally {
      setClaiming(false)
    }
  }

  if (!open) return null

  const curQr = payType === 2 ? aliQr : wxQr

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <div className="text-base font-semibold text-gray-800">导出需付费</div>
          <button onClick={() => close(false)} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <p className="text-sm text-gray-600">
            导出/下载材料需支付 <span className="font-semibold text-brand-600">¥{price}</span>。
            扫下方收款码支付后点「我已支付」，将立即发放 {tempCredits} 次临时额度，管理员核对到账后补足。
          </p>

          <div className="flex gap-2">
            <button
              onClick={() => setPayType(2)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm ${payType === 2 ? 'border-blue-500 text-blue-600' : 'border-gray-200 text-gray-700'}`}
            >支付宝</button>
            <button
              onClick={() => setPayType(1)}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm ${payType === 1 ? 'border-green-500 text-green-600' : 'border-gray-200 text-gray-700'}`}
            >微信支付</button>
          </div>

          <div className="flex min-h-[240px] items-center justify-center rounded-lg bg-gray-50">
            {loading ? (
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            ) : done ? (
              <div className="flex flex-col items-center gap-2 text-green-600">
                <CheckCircle2 className="h-10 w-10" />
                <span className="text-sm">已提交，临时额度已到账</span>
              </div>
            ) : curQr ? (
              <div className="flex flex-col items-center gap-2 py-3">
                <img src={curQr} alt="收款码" className="h-52 w-52" />
                <div className="text-sm text-gray-700">请支付 <span className="font-semibold text-brand-600">¥{price}</span></div>
              </div>
            ) : (
              <div className="px-4 text-center text-sm text-gray-400">收款码未配置，请联系管理员</div>
            )}
          </div>

          {error && <div className="text-sm text-red-500">{error}</div>}

          <button
            onClick={claim}
            disabled={claiming || done || loading}
            className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {claiming ? '提交中...' : '我已支付'}
          </button>
          <p className="text-[11px] text-gray-400">请务必按 ¥{price} 支付；恶意虚报将被管理员核对后取消额度。</p>
        </div>
      </div>
    </div>
  )
}
