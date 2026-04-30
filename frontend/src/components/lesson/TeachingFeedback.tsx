import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import { MessageSquare, ArrowRight, Loader2 } from 'lucide-react'
import { useT } from '../../i18n/translations'

interface TeachingFeedbackProps {
  lessonId: string
  lessonTitle: string
  scopeQs?: string
  forUserId?: string
}

export default function TeachingFeedback({ lessonId, lessonTitle, scopeQs = '', forUserId }: TeachingFeedbackProps) {
  const t = useT()
  const navigate = useNavigate()
  const [feedback, setFeedback] = useState('')
  const [nextTitle, setNextTitle] = useState('')
  const [nextTopic, setNextTopic] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedbackSaved, setFeedbackSaved] = useState(false)

  const handleSaveFeedback = async () => {
    if (!feedback.trim()) return
    setSubmitting(true)
    try {
      const form = new FormData()
      form.append('feedback', feedback)
      const qp = forUserId ? { for_user_id: forUserId } : undefined
      await api.post(`/api/v1/lessons/${lessonId}/feedback`, form, { params: qp })
      setFeedbackSaved(true)
    } catch (e) {
      console.error('Save feedback failed:', e)
    } finally {
      setSubmitting(false)
    }
  }

  const handleGenerateNext = async () => {
    if (!nextTitle.trim()) return
    setSubmitting(true)
    try {
      const form = new FormData()
      form.append('title', nextTitle)
      if (nextTopic) form.append('topic', nextTopic)
      if (feedback) form.append('teacher_feedback', feedback)
      const qp = forUserId ? { for_user_id: forUserId } : undefined
      const res = await api.post(`/api/v1/lessons/${lessonId}/next-lesson`, form, { params: qp })
      navigate(`/lesson/${res.data.id}/process${scopeQs}`)
    } catch (e) {
      console.error('Generate next lesson failed:', e)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="w-4 h-4 text-violet-600" />
        <h3 className="text-sm font-semibold text-gray-900">{t('comp.feedback_title')}</h3>
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-600">{t('comp.feedback_label')}</label>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder={t('comp.feedback_ph')}
          rows={3}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500 resize-none"
        />
        {!feedbackSaved && (
          <button
            onClick={handleSaveFeedback}
            disabled={!feedback.trim() || submitting}
            className="text-xs text-violet-600 hover:text-violet-700 font-medium disabled:opacity-50"
          >
            {t('comp.feedback_save')}
          </button>
        )}
        {feedbackSaved && (
          <span className="text-xs text-green-600">{t('comp.feedback_saved')}</span>
        )}
      </div>

      <div className="border-t border-gray-200 pt-4 space-y-3">
        <p className="text-xs font-medium text-gray-600">{t('comp.next_lesson')}</p>
        <input
          value={nextTitle}
          onChange={(e) => setNextTitle(e.target.value)}
          placeholder={t('comp.next_title_ph')}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
        />
        <input
          value={nextTopic}
          onChange={(e) => setNextTopic(e.target.value)}
          placeholder={t('comp.next_topic_ph')}
          className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
        />
        <button
          onClick={handleGenerateNext}
          disabled={!nextTitle.trim() || submitting}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-violet-600 rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <ArrowRight className="w-4 h-4" />
          )}
          {t('comp.next_generate')}
        </button>
      </div>
    </div>
  )
}
