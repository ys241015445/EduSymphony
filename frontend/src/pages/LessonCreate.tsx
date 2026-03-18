import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLessonStore } from '../stores/lessonStore'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Card from '../components/ui/Card'
import { Upload, FileText, ArrowLeft, Loader2, BookOpen } from 'lucide-react'

export default function LessonCreate() {
  const navigate = useNavigate()
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !subject || !gradeLevel) {
      setError('请填写所有必填项')
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
      if (sourceType === 'manual') {
        form.append('source_content', sourceContent)
      } else if (file) {
        form.append('file', file)
      }
      const lessonId = await createLesson(form)
      navigate(`/lesson/${lessonId}/process`)
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建失败')
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
          返回
        </button>

        <h1 className="text-2xl font-bold text-gray-900 mb-2">新建教案</h1>
        <p className="text-sm text-gray-500 mb-8">填写教学信息，AI专家团队将融合 5E、BOPPPS、PBL 三种教学理论为您协作生成一份完整的高质量教案。</p>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">基本信息</h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="教案标题 *" placeholder="例：光合作用" value={title} onChange={(e) => setTitle(e.target.value)} required />
              <Input label="学科 *" placeholder="例：生物" value={subject} onChange={(e) => setSubject(e.target.value)} required />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">学段 *</label>
                <select value={gradeLevel} onChange={(e) => setGradeLevel(e.target.value)} className={selectClasses} required>
                  <option value="">请选择</option>
                  <option value="primary">小学</option>
                  <option value="middle">初中</option>
                  <option value="high">高中</option>
                  <option value="college">大学</option>
                </select>
              </div>
              <Input label="具体年级" placeholder="例：高一" value={specificGrade} onChange={(e) => setSpecificGrade(e.target.value)} />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">地区</label>
                <select value={region} onChange={(e) => setRegion(e.target.value)} className={selectClasses}>
                  <option value="mainland">中国大陆</option>
                  <option value="hongkong">香港</option>
                  <option value="macau">澳门</option>
                  <option value="taiwan">台湾</option>
                </select>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">教学设计信息</h2>
            <div className="space-y-4">
              <Input label="教案主题" placeholder="例：通过实验理解光合作用的原理与过程" value={topic} onChange={(e) => setTopic(e.target.value)} />
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">学生类别</label>
                <select value={studentType} onChange={(e) => setStudentType(e.target.value)} className={selectClasses}>
                  <option value="">请选择</option>
                  <option value="普通班">普通班</option>
                  <option value="重点班">重点班</option>
                  <option value="艺术特长生">艺术特长生</option>
                  <option value="体育特长生">体育特长生</option>
                  <option value="国际班">国际班</option>
                  <option value="融合教育班">融合教育班</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">需要避免的问题</label>
                <textarea
                  value={avoidIssues}
                  onChange={(e) => setAvoidIssues(e.target.value)}
                  placeholder="例：避免过多使用专业术语；避免课堂活动时间不足..."
                  rows={3}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400 resize-none"
                />
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-center gap-2 mb-4">
              <BookOpen className="w-5 h-5 text-brand-600" />
              <h2 className="font-semibold text-gray-900">教学模型</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">系统将融合以下三种教学理论，生成一份完整教案（非分开生成），所有AI教师均具备三种理论的教学技巧。</p>
            <div className="grid sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg border-2 border-blue-200 bg-blue-50">
                <p className="text-sm font-semibold text-blue-700">5E教学模型</p>
                <p className="text-xs text-gray-500 mt-1">引入→探索→解释→拓展→评价</p>
              </div>
              <div className="p-3 rounded-lg border-2 border-emerald-200 bg-emerald-50">
                <p className="text-sm font-semibold text-emerald-700">BOPPPS模型</p>
                <p className="text-xs text-gray-500 mt-1">导入→目标→前测→参与→后测→总结</p>
              </div>
              <div className="p-3 rounded-lg border-2 border-violet-200 bg-violet-50">
                <p className="text-sm font-semibold text-violet-700">PBL教学模型</p>
                <p className="text-xs text-gray-500 mt-1">问题情境→任务→实施→展示→反思</p>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-3">三种理论融合在每个教学环节中：导入与情境创设 → 目标与前测 → 探究与任务设计 → 参与式学习 → 解释与展示 → 拓展应用 → 评价与反思 → 总结</p>
          </Card>

          <Card>
            <h2 className="font-semibold text-gray-900 mb-4">教案内容</h2>
            <div className="flex gap-3 mb-4">
              <button
                type="button"
                onClick={() => setSourceType('manual')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${sourceType === 'manual' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                <FileText className="w-4 h-4" />
                手动输入
              </button>
              <button
                type="button"
                onClick={() => setSourceType('upload')}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${sourceType === 'upload' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}
              >
                <Upload className="w-4 h-4" />
                上传文件
              </button>
            </div>

            {sourceType === 'manual' ? (
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700">教案内容 / 教学要点</label>
                <textarea
                  value={sourceContent}
                  onChange={(e) => setSourceContent(e.target.value)}
                  placeholder="请输入教案内容或教学要点，AI将基于此生成完整的结构化教案..."
                  rows={8}
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 placeholder:text-gray-400 resize-none"
                  required
                />
              </div>
            ) : (
              <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center hover:border-brand-300 transition-colors">
                <Upload className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500 mb-2">拖拽文件到此处，或点击选择文件</p>
                <p className="text-xs text-gray-400 mb-4">支持 TXT、DOCX、PDF 格式</p>
                <input
                  type="file"
                  accept=".txt,.doc,.docx,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload">
                  <Button variant="secondary" size="sm" type="button" onClick={() => document.getElementById('file-upload')?.click()}>
                    选择文件
                  </Button>
                </label>
                {file && <p className="mt-3 text-sm text-brand-600">{file.name}</p>}
              </div>
            )}
          </Card>

          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={() => navigate(-1)}>取消</Button>
            <Button type="submit" disabled={loading} size="lg">
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  创建中...
                </>
              ) : (
                '开始生成教案'
              )}
            </Button>
          </div>
        </form>
      </main>
    </div>
  )
}
