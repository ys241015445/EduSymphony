import { useState, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useLessonStore, LessonsScope } from '../stores/lessonStore'
import { useLanguageStore } from '../stores/languageStore'
import { useT } from '../i18n/translations'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Card from '../components/ui/Card'
import { Upload, FileText, ArrowLeft, Loader2, BookOpen, Sparkles, PenLine } from 'lucide-react'

const THEORY_CATEGORIES: {
  labelKey: string
  color: string
  theories: { value: string; key: string }[]
}[] = [
  {
    labelKey: 'create.cat_constructivism',
    color: 'violet',
    theories: [
      { value: '社会建构主义（维果茨基）', key: 'create.t_social_constructivism' },
      { value: '支架式教学', key: 'create.t_scaffolding' },
      { value: '皮亚杰认知建构主义', key: 'create.t_piaget' },
      { value: '蒙台梭利教育法', key: 'create.t_montessori' },
      { value: '建构主义认知冲突模型', key: 'create.t_cognitive_conflict' },
    ],
  },
  {
    labelKey: 'create.cat_project',
    color: 'emerald',
    theories: [
      { value: '项目式学习（PBL）简化版', key: 'create.t_pbl_simple' },
      { value: '项目式学习（PBL）高阶', key: 'create.t_pbl_advanced' },
      { value: '基于问题的学习（PBL）', key: 'create.t_problem_based' },
      { value: '探究式学习', key: 'create.t_inquiry' },
      { value: '发现学习（布鲁纳）', key: 'create.t_discovery' },
    ],
  },
  {
    labelKey: 'create.cat_cognitive',
    color: 'blue',
    theories: [
      { value: '布鲁姆掌握学习理论', key: 'create.t_bloom' },
      { value: '认知负荷理论', key: 'create.t_cognitive_load' },
      { value: '认知学徒制', key: 'create.t_cognitive_apprenticeship' },
      { value: 'CPA教学法（具象-形象-抽象）', key: 'create.t_cpa' },
      { value: '马扎诺教育目标模型', key: 'create.t_marzano' },
      { value: '变式教学', key: 'create.t_variation' },
      { value: '直接教学法', key: 'create.t_direct_instruction' },
    ],
  },
  {
    labelKey: 'create.cat_social',
    color: 'amber',
    theories: [
      { value: '社会学习理论（班杜拉）', key: 'create.t_bandura' },
      { value: '体验式学习圈（库伯）', key: 'create.t_kolb' },
      { value: '道德两难讨论法', key: 'create.t_moral_dilemma' },
      { value: '合作学习', key: 'create.t_cooperative' },
    ],
  },
  {
    labelKey: 'create.cat_teaching',
    color: 'rose',
    theories: [
      { value: '5E教学模式', key: 'create.t_5e' },
      { value: '翻转课堂', key: 'create.t_flipped' },
      { value: '任务型语言教学（TBLT）', key: 'create.t_tblt' },
      { value: '阅读工作坊模型', key: 'create.t_reading_workshop' },
      { value: '瑞吉欧取向', key: 'create.t_reggio' },
      { value: '工作室思维模型', key: 'create.t_studio_thinking' },
    ],
  },
  {
    labelKey: 'create.cat_frontier',
    color: 'indigo',
    theories: [
      { value: '联通主义', key: 'create.t_connectivism' },
      { value: '批判性探究', key: 'create.t_critical_inquiry' },
    ],
  },
]

const CATEGORY_STYLES: Record<string, { badge: string; pill: string; pillActive: string }> = {
  violet:  { badge: 'bg-violet-100 text-violet-700', pill: 'border-violet-200 hover:border-violet-400 hover:bg-violet-50', pillActive: 'border-violet-500 bg-violet-50 text-violet-700 ring-1 ring-violet-500/30' },
  emerald: { badge: 'bg-emerald-100 text-emerald-700', pill: 'border-emerald-200 hover:border-emerald-400 hover:bg-emerald-50', pillActive: 'border-emerald-500 bg-emerald-50 text-emerald-700 ring-1 ring-emerald-500/30' },
  blue:    { badge: 'bg-blue-100 text-blue-700', pill: 'border-blue-200 hover:border-blue-400 hover:bg-blue-50', pillActive: 'border-blue-500 bg-blue-50 text-blue-700 ring-1 ring-blue-500/30' },
  amber:   { badge: 'bg-amber-100 text-amber-700', pill: 'border-amber-200 hover:border-amber-400 hover:bg-amber-50', pillActive: 'border-amber-500 bg-amber-50 text-amber-700 ring-1 ring-amber-500/30' },
  rose:    { badge: 'bg-rose-100 text-rose-700', pill: 'border-rose-200 hover:border-rose-400 hover:bg-rose-50', pillActive: 'border-rose-500 bg-rose-50 text-rose-700 ring-1 ring-rose-500/30' },
  indigo:  { badge: 'bg-indigo-100 text-indigo-700', pill: 'border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50', pillActive: 'border-indigo-500 bg-indigo-50 text-indigo-700 ring-1 ring-indigo-500/30' },
}

export default function LessonCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const forUserId = searchParams.get('for_user_id') || undefined
  const lessonScope = useMemo<LessonsScope | undefined>(
    () => (forUserId ? { for_user_id: forUserId } : undefined),
    [forUserId],
  )
  const scopeQs = forUserId ? `?for_user_id=${encodeURIComponent(forUserId)}` : ''
  const t = useT()
  const { createLesson } = useLessonStore()

  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [gradeLevel, setGradeLevel] = useState('')
  const [specificGrade, setSpecificGrade] = useState('')
  const [region, setRegion] = useState('mainland')
  const [topic, setTopic] = useState('')
  const [avoidIssues, setAvoidIssues] = useState('')
  const [studentType, setStudentType] = useState('')
  const [sourceType, setSourceType] = useState<'manual' | 'upload'>('manual')
  const [sourceContent, setSourceContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [generationMode, setGenerationMode] = useState<'full_auto' | 'semi_auto'>('full_auto')
  const [preferredTheory, setPreferredTheory] = useState('')
  const [customTheory, setCustomTheory] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const effectiveTheory = showCustomInput ? customTheory : preferredTheory

  const theoryDisplayName = (value: string) => {
    for (const cat of THEORY_CATEGORIES) {
      const found = cat.theories.find((th) => th.value === value)
      if (found) return t(found.key)
    }
    return value
  }

  const handleTheoryClick = (value: string) => {
    setShowCustomInput(false)
    setCustomTheory('')
    setPreferredTheory(prev => prev === value ? '' : value)
  }

  const handleCustomClick = () => {
    setPreferredTheory('')
    setShowCustomInput(prev => !prev)
    if (showCustomInput) setCustomTheory('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !subject || !gradeLevel) {
      setError(t('create.fill_required'))
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
      if (topic) form.append('topic', topic)
      if (avoidIssues) form.append('avoid_issues', avoidIssues)
      if (studentType) form.append('student_type', studentType)
      form.append('source_type', sourceType)
      form.append('generation_mode', generationMode)
      form.append('locale', useLanguageStore.getState().locale)
      if (effectiveTheory) form.append('preferred_theory', effectiveTheory)
      if (sourceType === 'manual') {
        form.append('source_content', sourceContent)
      } else if (file) {
        form.append('file', file)
      }
      const lessonId = await createLesson(form, lessonScope)
      navigate(`/lesson/${lessonId}/process${scopeQs}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('create.error_create'))
    } finally {
      setLoading(false)
    }
  }

  const selectClasses = 'w-full px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500'

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6">
          <ArrowLeft className="w-4 h-4" />
          {t('create.back')}
        </button>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('create.title')}</h1>
        <p className="text-sm text-gray-500 mb-8">{t('create.subtitle')}</p>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('create.basic_info')}</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label={t('create.lesson_title')} placeholder={t('create.lesson_title_ph')} value={title} onChange={(e) => setTitle(e.target.value)} required />
              <Input label={t('create.subject_label')} placeholder={t('create.subject_ph')} value={subject} onChange={(e) => setSubject(e.target.value)} required />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">{t('create.grade_label')}</label>
                <select value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)} className={selectClasses} required>
                  <option value="">{t('create.grade_select')}</option>
                  <option value="primary">{t('create.grade_primary')}</option>
                  <option value="middle">{t('create.grade_middle')}</option>
                  <option value="high">{t('create.grade_high')}</option>
                  <option value="college">{t('create.grade_college')}</option>
                </select>
              </div>
              <Input label={t('create.specific_grade')} placeholder={t('create.specific_grade_ph')} value={specificGrade} onChange={(e) => setSpecificGrade(e.target.value)} />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">{t('create.region_label')}</label>
                <select value={region} onChange={(e) => setRegion(e.target.value)} className={selectClasses}>
                  <option value="mainland">{t('create.region_mainland')}</option>
                  <option value="hongkong">{t('create.region_hongkong')}</option>
                  <option value="macau">{t('create.region_macau')}</option>
                  <option value="taiwan">{t('create.region_taiwan')}</option>
                </select>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('create.design_info')}</h2>
            <div className="space-y-4">
              <Input label={t('create.topic_label')} placeholder={t('create.topic_ph')} value={topic} onChange={(e) => setTopic(e.target.value)} />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">{t('create.student_type')}</label>
                <select value={studentType} onChange={(e) => setStudentType(e.target.value)} className={selectClasses}>
                  <option value="">{t('create.student_select')}</option>
                  <option value="普通班">{t('create.student_regular')}</option>
                  <option value="重点班">{t('create.student_advanced')}</option>
                  <option value="艺术特长生">{t('create.student_art')}</option>
                  <option value="体育特长生">{t('create.student_sports')}</option>
                  <option value="国际班">{t('create.student_international')}</option>
                  <option value="融合教育班">{t('create.student_inclusive')}</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">{t('create.avoid_label')}</label>
                <textarea
                  value={avoidIssues}
                  onChange={(e) => setAvoidIssues(e.target.value)}
                  placeholder={t('create.avoid_ph')}
                  rows={3}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400 resize-none"
                />
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="w-5 h-5 text-brand-600" />
              <h2 className="font-semibold text-gray-900">{t('create.theory_title')}</h2>
            </div>

            {generationMode === 'full_auto' ? (
              <div className="p-4 rounded-lg bg-gradient-to-r from-brand-50 to-violet-50 border border-brand-100">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-brand-600" />
                  <p className="text-sm font-medium text-brand-700">{t('create.ai_auto_title')}</p>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {t('create.ai_auto_desc')}
                </p>
                <p className="text-xs text-gray-500 mt-2">{t('create.ai_auto_hint')}</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 rounded-lg bg-violet-50 border border-violet-100">
                  <p className="text-sm text-violet-700 leading-relaxed">
                    {t('create.theory_hint')}
                  </p>
                </div>

                <div className="space-y-5">
                  {THEORY_CATEGORIES.map((cat) => {
                    const styles = CATEGORY_STYLES[cat.color]
                    return (
                      <div key={cat.labelKey}>
                        <div className="flex items-center gap-2 mb-2.5">
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${styles.badge}`}>
                            {t(cat.labelKey)}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {cat.theories.map((theory) => {
                            const isActive = preferredTheory === theory.value && !showCustomInput
                            return (
                              <button
                                key={theory.value}
                                type="button"
                                onClick={() => handleTheoryClick(theory.value)}
                                className={`px-3 py-1.5 rounded-full border text-xs font-medium transition-all duration-150 ${
                                  isActive ? styles.pillActive : `${styles.pill} text-gray-600`
                                }`}
                              >
                                {t(theory.key)}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="pt-2 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={handleCustomClick}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all duration-150 ${
                      showCustomInput
                        ? 'border-brand-500 bg-brand-50 text-brand-700 ring-1 ring-brand-500/30'
                        : 'border-gray-200 text-gray-500 hover:border-gray-400 hover:bg-gray-50'
                    }`}
                  >
                    <PenLine className="w-3 h-3" />
                    {t('create.other_custom')}
                  </button>

                  {showCustomInput && (
                    <div className="mt-3">
                      <input
                        type="text"
                        value={customTheory}
                        onChange={(e) => setCustomTheory(e.target.value)}
                        placeholder={t('create.custom_ph')}
                        className="w-full px-4 py-2.5 rounded-lg border border-brand-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400"
                        autoFocus
                      />
                    </div>
                  )}
                </div>

                {effectiveTheory && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-gradient-to-r from-brand-50 to-violet-50 border border-brand-200">
                    <Sparkles className="w-4 h-4 text-brand-600 flex-shrink-0" />
                    <p className="text-sm text-brand-700">
                      {t('create.theory_selected')}<span className="font-semibold">{theoryDisplayName(effectiveTheory)}</span>
                    </p>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('create.content_title')}</h2>
            <div className="flex gap-3 mb-4">
              <button
                type="button"
                onClick={() => setSourceType('manual')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${sourceType === 'manual' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                <FileText className="w-4 h-4" />
                {t('create.source_manual')}
              </button>
              <button
                type="button"
                onClick={() => setSourceType('upload')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${sourceType === 'upload' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                <Upload className="w-4 h-4" />
                {t('create.source_upload')}
              </button>
            </div>

            {sourceType === 'manual' ? (
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">{t('create.content_label')}</label>
                <textarea
                  value={sourceContent}
                  onChange={(e) => setSourceContent(e.target.value)}
                  placeholder={t('create.content_ph')}
                  rows={8}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400 resize-none"
                />
              </div>
            ) : (
              <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-brand-300 transition-colors">
                <Upload className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500 mb-2">{t('create.upload_drag')}</p>
                <p className="text-xs text-gray-400 mb-4">{t('create.upload_hint')}</p>
                <input
                  type="file"
                  accept=".txt,.doc,.docx,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload">
                  <Button variant="secondary" size="sm" type="button" onClick={() => document.getElementById('file-upload')?.click()}>
                    {t('create.upload_select')}
                  </Button>
                </label>
                {file && <p className="mt-3 text-sm text-brand-600">{file.name}</p>}
              </div>
            )}
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">{t('create.mode_title')}</h2>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setGenerationMode('full_auto')}
                className={`flex-1 p-4 rounded-xl border-2 text-left transition-all ${generationMode === 'full_auto' ? 'border-brand-400 bg-brand-50 shadow-sm' : 'border-gray-200 hover:border-gray-300'}`}
              >
                <p className="text-sm font-semibold text-gray-900">{t('create.mode_auto')}</p>
                <p className="text-xs text-gray-500 mt-1">{t('create.mode_auto_desc')}</p>
              </button>
              <button
                type="button"
                onClick={() => setGenerationMode('semi_auto')}
                className={`flex-1 p-4 rounded-xl border-2 text-left transition-all ${generationMode === 'semi_auto' ? 'border-violet-400 bg-violet-50 shadow-sm' : 'border-gray-200 hover:border-gray-300'}`}
              >
                <p className="text-sm font-semibold text-gray-900">{t('create.mode_semi')}</p>
                <p className="text-xs text-gray-500 mt-1">{t('create.mode_semi_desc')}</p>
              </button>
            </div>
          </Card>

          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => navigate(-1)}>{t('create.cancel')}</Button>
            <Button type="submit" disabled={loading} size="lg">
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {t('create.creating')}
                </>
              ) : (
                t('create.submit')
              )}
            </Button>
          </div>
        </form>
      </main>
    </div>
  )
}
