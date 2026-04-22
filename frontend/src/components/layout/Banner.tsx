import { useState, useEffect } from 'react'
import { api } from '../../services/api'
import { X, Info } from 'lucide-react'

export default function Banner() {
  const [text, setText] = useState('')
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    api.get('/api/v1/system/banner')
      .then(res => {
        if (res.data?.enabled && res.data?.text) {
          setText(res.data.text)
        }
      })
      .catch(() => {})
  }, [])

  if (!text || dismissed) return null

  return (
    <div className="bg-brand-600 text-white px-4 py-2 text-sm flex items-center justify-center gap-2 relative">
      <Info className="w-4 h-4 flex-shrink-0" />
      <span>{text}</span>
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-white/20 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
