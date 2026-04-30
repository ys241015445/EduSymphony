import { useState, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { GraduationCap, Upload, Loader2 } from 'lucide-react'
import { useLanguageStore } from '../stores/languageStore'
import { useT } from '../i18n/translations'

type Scope = 'single_lesson' | 'multi_week' | 'semester'
type CourseType = 'required' | 'elective'
type CourseNature = 'theory' | 'practical' | 'mixed'

const UNI_GRADES = [
  'freshman', 'sophomore', 'junior', 'senior',
  'master_1', 'master_2', 'master_3', 'phd',
]

export default function UniversityCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  const t = useT()

  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [specificGrade, setSpecificGrade] = useState('freshman')
  const [major, setMajor] = useState('')
  const [courseType, setCourseType] = useState<CourseType>('required')
  const [courseNature, setCourseNature] = useState<CourseNature>('theory')
  const [region, setRegion] = useState('mainland')

  const [scope, setScope] = useState<Scope>('single_lesson')
  const [weeks, setWeeks] = useState(4)
  const [lessonsPerWeek, setLessonsPerWeek] = useState(2)
  const [semesterWeeks, setSemesterWeeks] = useState(16)

  const [sourceContent, setSourceContent] = useState('')
  const [scheduleText, setScheduleText] = useState('')
  const [outlineText, setOutlineText] = useState('')
  const [objectives, setObjectives] = useState('')
  const [qualityGoals, setQualityGoals] = useState('')
  const [specialRequirements, setSpecialRequirements] = useState('')

  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const resolved = useMemo(() => {
    if (scope === 'single_lesson') return { total_weeks: 1, lessons_per_week: 1 }
    if (scope === 'multi_week') return { total_weeks: weeks, lessons_per_week: lessonsPerWeek }
    return { total_weeks: semesterWeeks, lessons_per_week: lessonsPerWeek }
  }, [scope, weeks, lessonsPerWeek, semesterWeeks])
  const totalLessons = resolved.total_weeks * resolved.lessons_per_week

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !subject || !major) {
      setError(t('university.fill_required'))
      return
    }
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('title', title)
      form.append('subject', subject)
      form.append('grade_level', '大学')
      form.append('specific_grade', t(`university.grade_${specificGrade}`))
      form.append('region', region)
      form.append('total_weeks', String(resolved.total_weeks))
      form.append('lessons_per_week', String(resolved.lessons_per_week))
      if (objectives) form.append('objectives', objectives)
      if (qualityGoals) form.append('quality_goals', qualityGoals)
      form.append('mode', 'full_auto')
      form.append('locale', useLanguageStore.getState().locale)
      form.append('education_level', 'university')
      form.append('major', major)
      form.append('course_type', courseType)
      form.append('course_nature', courseNature)
      if (scheduleText) form.append('schedule_text', scheduleText)
      if (outlineText) form.append('outline_text', outlineText)
      if (specialRequirements) form.append('special_requirements', specialRequirements)
      if (file) {
        form.append('file', file)
      } else if (sourceContent) {
        form.append('source_content', sourceContent)
      }
      const res = await api.post('/api/v1/series', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: forUserId ? { for_user_id: forUserId } : undefined,
      })
      navigate(`/university/${res.data.id}${scopeQs}`)
    } catch (e: any) {
      setError(e.response?.data?.detail || t('university.create_failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <GraduationCap className="w-6 h-6 text-brand-600" />
          <h1 className="text-2xl font-bold text-gray-900">{t('university.create_title')}</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">{t('university.create_subtitle')}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('university.basic_info')}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.name_label')}*</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('university.name_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.subject_label')}*</label>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder={t('university.subject_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.major_label')}*</label>
                <input value={major} onChange={(e) => setMajor(e.target.value)} placeholder={t('university.major_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.grade_label')}</label>
                <select value={specificGrade} onChange={(e) => setSpecificGrade(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  {UNI_GRADES.map(g => (
                    <option key={g} value={g}>{t(`university.grade_${g}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.region_label')}</label>
                <select value={region} onChange={(e) => setRegion(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="mainland">{t('series.region_mainland')}</option>
                  <option value="taiwan">{t('series.region_taiwan')}</option>
                  <option value="hongkong">{t('series.region_hongkong')}</option>
                  <option value="international">{t('series.region_international')}</option>
                </select>
              </div>

              <div className="col-span-2 grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.course_type_label')}</label>
                  <div className="flex gap-2">
                    {(['required', 'elective'] as CourseType[]).map(v => (
                      <button key={v} type="button" onClick={() => setCourseType(v)}
                        className={`flex-1 px-3 py-2 rounded-lg border text-sm transition-all ${
                          courseType === v ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
                        }`}>
                        {t(`university.course_type_${v}`)}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.course_nature_label')}</label>
                  <div className="flex gap-2">
                    {(['theory', 'practical', 'mixed'] as CourseNature[]).map(v => (
                      <button key={v} type="button" onClick={() => setCourseNature(v)}
                        className={`flex-1 px-3 py-2 rounded-lg border text-sm transition-all ${
                          courseNature === v ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:border-brand-400'
                        }`}>
                        {t(`university.course_nature_${v}`)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('university.scope_title')}</h2>
            <div className="grid grid-cols-3 gap-3 mb-4">
              {(['single_lesson', 'multi_week', 'semester'] as Scope[]).map(s => (
                <button key={s} type="button" onClick={() => setScope(s)}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    scope === s ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
                  }`}>
                  <p className="text-sm font-semibold text-gray-900">{t(`university.scope_${s}`)}</p>
                  <p className="text-xs text-gray-500 mt-1">{t(`university.scope_${s}_desc`)}</p>
                </button>
              ))}
            </div>
            {scope === 'multi_week' && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.weeks_label')}</label>
                  <input type="number" min={1} max={20} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.lessons_per_week')}</label>
                  <input type="number" min={1} max={10} value={lessonsPerWeek} onChange={(e) => setLessonsPerWeek(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              </div>
            )}
            {scope === 'semester' && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.semester_weeks_label')}</label>
                  <input type="number" min={12} max={24} value={semesterWeeks} onChange={(e) => setSemesterWeeks(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.lessons_per_week')}</label>
                  <input type="number" min={1} max={10} value={lessonsPerWeek} onChange={(e) => setLessonsPerWeek(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
              </div>
            )}
            <div className="mt-3 text-sm text-gray-500">
              {t('university.total_lessons_prefix')} <span className="font-semibold text-brand-600">{totalLessons}</span> {t('university.total_lessons_unit')}
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('university.optional_title')}</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.schedule_label')}</label>
                <textarea rows={3} value={scheduleText} onChange={(e) => setScheduleText(e.target.value)}
                  placeholder={t('university.schedule_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.outline_label')}</label>
                <textarea rows={3} value={outlineText} onChange={(e) => setOutlineText(e.target.value)}
                  placeholder={t('university.outline_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.objectives_label')}</label>
                <textarea rows={2} value={objectives} onChange={(e) => setObjectives(e.target.value)}
                  placeholder={t('university.objectives_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.quality_goals_label')}</label>
                <textarea rows={2} value={qualityGoals} onChange={(e) => setQualityGoals(e.target.value)}
                  placeholder={t('university.quality_goals_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('university.special_req_label')}</label>
                <textarea rows={2} value={specialRequirements} onChange={(e) => setSpecialRequirements(e.target.value)}
                  placeholder={t('university.special_req_ph')}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('university.content_title')}</h2>
            <div className="space-y-3">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-brand-400 transition-colors">
                <input
                  type="file"
                  accept=".txt,.md,.pdf,.docx,.doc"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden" id="uni-upload"
                />
                <label htmlFor="uni-upload" className="cursor-pointer">
                  <Upload className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                  <p className="text-sm text-gray-600">{file ? file.name : t('university.upload_text')}</p>
                  <p className="text-xs text-gray-400 mt-1">{t('university.upload_hint')}</p>
                </label>
              </div>
              <div className="text-center text-xs text-gray-400">{t('university.or_manual')}</div>
              <textarea value={sourceContent} onChange={(e) => setSourceContent(e.target.value)} rows={4}
                placeholder={t('university.manual_ph')}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
            </div>
          </Card>

          {error && <p className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>}

          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => navigate('/dashboard')}>{t('series.cancel')}</Button>
            <Button type="submit" disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <GraduationCap className="w-4 h-4 mr-1.5" />}
              {t('university.create_submit')}
            </Button>
          </div>
        </form>
      </main>
    </div>
  )
}
