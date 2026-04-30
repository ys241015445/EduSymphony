import { useState } from 'react'
import { MessageSquarePlus, RefreshCw, Send } from 'lucide-react'
import Button from '../ui/Button'
import { api } from '../../services/api'
import { useT } from '../../i18n/translations'

interface Props {
  lessonId: string
  sectionKey: string
  /** Admin scoped lesson: target user's id */
  forUserId?: string
  onSubmitted?: () => void
}

export default function AnnotationEditor({ lessonId, sectionKey, forUserId, onSubmitted }: Props) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [content, setContent] = useState('')
  const [requestRegenerate, setRequestRegenerate] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!content.trim()) return
    setLoading(true)
    try {
      await api.post(`/api/v1/lessons/${lessonId}/annotations`, {
        section_key: sectionKey,
        content,
        request_regenerate: requestRegenerate,
      }, {
        params: forUserId ? { for_user_id: forUserId } : undefined,
      })
      setContent('')
      setRequestRegenerate(false)
      setOpen(false)
      onSubmitted?.()
    } catch {
      alert(t('comp.annotation_failed'))
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-brand-600 transition-colors"
      >
        <MessageSquarePlus className="w-3.5 h-3.5" />
        {t('comp.annotation_title')}
      </button>
    )
  }

  return (
    <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={t('comp.annotation_ph')}
        rows={3}
        className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
      />
      <div className="flex items-center justify-between mt-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={requestRegenerate}
            onChange={(e) => setRequestRegenerate(e.target.checked)}
            className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-xs text-gray-600 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" />
            {t('comp.annotation_regen')}
          </span>
        </label>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>{t('comp.annotation_cancel')}</Button>
          <Button size="sm" onClick={handleSubmit} disabled={loading || !content.trim()}>
            <Send className="w-3 h-3 mr-1" />
            {t('comp.annotation_submit')}
          </Button>
        </div>
      </div>
    </div>
  )
}
