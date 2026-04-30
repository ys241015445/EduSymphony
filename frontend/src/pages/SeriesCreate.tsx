import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { BookOpen, Upload, Loader2 } from 'lucide-react'
import { useLanguageStore } from '../stores/languageStore'
import { useT } from '../i18n/translations'

export default function SeriesCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  const t = useT()
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [gradeLevel, setGradeLevel] = useState('')
  const [specificGrade, setSpecificGrade] = useState('')
  const [region, setRegion] = useState('mainland')
  const [totalWeeks, setTotalWeeks] = useState(16)
  const [lessonsPerWeek, setLessonsPerWeek] = useState(2)
  const [objectives, setObjectives] = useState('')
  const [qualityGoals, setQualityGoals] = useState('')
  const [mode, setMode] = useState<'full_auto' | 'semi_auto'>('full_auto')
  const [file, setFile] = useState<File | null>(null)
  const [sourceContent, setSourceContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !subject || !gradeLevel) {
      setError(t('series.fill_required'))
      return
    }
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('title', title)
      form.append('subject', subject)
      form.append('grade_level', gradeLevel)
      if (specificGrade) form.append('specific_grade', specificGrade)
      form.append('region', region)
      form.append('total_weeks', String(totalWeeks))
      form.append('lessons_per_week', String(lessonsPerWeek))
      if (objectives) form.append('objectives', objectives)
      if (qualityGoals) form.append('quality_goals', qualityGoals)
      form.append('mode', mode)
      form.append('locale', useLanguageStore.getState().locale)
      if (file) {
        form.append('file', file)
      } else if (sourceContent) {
        form.append('source_content', sourceContent)
      }
      const res = await api.post('/api/v1/series', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: forUserId ? { for_user_id: forUserId } : undefined,
      })
      navigate(`/series/${res.data.id}${scopeQs}`)
    } catch (e: any) {
      setError(e.response?.data?.detail || t('series.create_failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <BookOpen className="w-6 h-6 text-brand-600" />
          <h1 className="text-2xl font-bold text-gray-900">{t('series.create_title')}</h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('series.basic_info')}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.name_label')}</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('series.name_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.subject_label')}</label>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder={t('series.subject_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.grade_label')}</label>
                <select value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">{t('series.grade_select')}</option>
                  <option value="小学">{t('series.grade_primary')}</option>
                  <option value="初中">{t('series.grade_middle')}</option>
                  <option value="高中">{t('series.grade_high')}</option>
                  <option value="大学">{t('series.grade_college')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.specific_grade')}</label>
                <input value={specificGrade} onChange={(e) => setSpecificGrade(e.target.value)} placeholder={t('series.specific_grade_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.region_label')}</label>
                <select value={region} onChange={(e) => setRegion(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="mainland">{t('series.region_mainland')}</option>
                  <option value="taiwan">{t('series.region_taiwan')}</option>
                  <option value="hongkong">{t('series.region_hongkong')}</option>
                  <option value="international">{t('series.region_international')}</option>
                </select>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('series.plan_title')}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.total_weeks')}</label>
                <input type="number" min={1} max={52} value={totalWeeks} onChange={(e) => setTotalWeeks(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.lessons_per_week')}</label>
                <input type="number" min={1} max={10} value={lessonsPerWeek} onChange={(e) => setLessonsPerWeek(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div className="col-span-2 text-sm text-gray-500">
                {t('series.total_lessons')} <span className="font-semibold text-brand-600">{totalWeeks * lessonsPerWeek}</span> {t('series.total_lessons_unit')}
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.objectives')}</label>
                <textarea value={objectives} onChange={(e) => setObjectives(e.target.value)} rows={2}
                  placeholder={t('series.objectives_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('series.quality_goals')}</label>
                <textarea value={qualityGoals} onChange={(e) => setQualityGoals(e.target.value)} rows={2}
                  placeholder={t('series.quality_goals_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('series.material_title')}</h2>
            <div className="space-y-3">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-brand-400 transition-colors">
                <input
                  type="file"
                  accept=".txt,.md,.pdf,.docx,.doc"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden" id="book-upload"
                />
                <label htmlFor="book-upload" className="cursor-pointer">
                  <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                  <p className="text-sm text-gray-600">{file ? file.name : t('series.upload_text')}</p>
                  <p className="text-xs text-gray-400 mt-1">{t('series.upload_hint')}</p>
                </label>
              </div>
              <div className="text-center text-xs text-gray-400">{t('series.or_manual')}</div>
              <textarea value={sourceContent} onChange={(e) => setSourceContent(e.target.value)} rows={4}
                placeholder={t('series.manual_ph')}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('series.mode_title')}</h2>
            <div className="flex gap-3">
              <button type="button" onClick={() => setMode('full_auto')}
                className={`flex-1 p-4 rounded-xl border-2 text-left transition-all ${mode === 'full_auto' ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="text-sm font-semibold text-gray-900">{t('series.mode_auto')}</p>
                <p className="text-xs text-gray-500 mt-1">{t('series.mode_auto_desc')}</p>
              </button>
              <button type="button" onClick={() => setMode('semi_auto')}
                className={`flex-1 p-4 rounded-xl border-2 text-left transition-all ${mode === 'semi_auto' ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="text-sm font-semibold text-gray-900">{t('series.mode_semi')}</p>
                <p className="text-xs text-gray-500 mt-1">{t('series.mode_semi_desc')}</p>
              </button>
            </div>
          </Card>

          {error && <p className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>}

          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => navigate('/dashboard')}>{t('series.cancel')}</Button>
            <Button type="submit" disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <BookOpen className="w-4 h-4 mr-1.5" />}
              {t('series.create_submit')}
            </Button>
          </div>
        </form>
      </main>
    </div>
  )
}
