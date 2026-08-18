import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, BookOpen, CheckCircle2, Download, Loader2, Upload } from 'lucide-react'
import Header from '../components/layout/Header'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import LockedComingSoon from '../components/semester/LockedComingSoon'
import { useAuthStore } from '../stores/authStore'
import { hasCapability } from '../lib/access'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import { toast } from '../components/ui/Toast'

type Project = {
  id: string
  course_name: string
  mode: string
  status: string
  error?: string | null
  schedule?: any
  syllabus?: any
  weeks?: any
  lessons?: any
  has_syllabus_file?: boolean
  has_calendar_theory?: boolean
  has_calendar_lab?: boolean
  has_lessons_file?: boolean
  has_material_html?: boolean
  has_ppt?: boolean
}

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

export default function ZhukeMaterials() {
  const t = useT()
  const user = useAuthStore((s) => s.user)
  const allowed = hasCapability(user as any, 'can_zhuke_materials')

  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [project, setProject] = useState<Project | null>(null)

  const [courseName, setCourseName] = useState('')
  const [courseCode, setCourseCode] = useState('')
  const [credits, setCredits] = useState('')
  const [totalHours, setTotalHours] = useState('')
  const [theoryHours, setTheoryHours] = useState('')
  const [labHours, setLabHours] = useState('')
  const [mode, setMode] = useState('C')
  const [notes, setNotes] = useState('')
  const [files, setFiles] = useState<FileList | null>(null)

  const [weekday, setWeekday] = useState('周一')
  const [periodStart, setPeriodStart] = useState(1)
  const [periodEnd, setPeriodEnd] = useState(2)
  const [classroom, setClassroom] = useState('')
  const [teacher, setTeacher] = useState('')
  const [className, setClassName] = useState('')

  const steps = useMemo(
    () => [
      t('zhuke_materials.step_upload'),
      t('zhuke_materials.step_syllabus'),
      t('zhuke_materials.step_schedule'),
      t('zhuke_materials.step_calendar'),
      t('zhuke_materials.step_lessons'),
      t('zhuke_materials.step_download'),
    ],
    [t],
  )

  if (!allowed) {
    return <LockedComingSoon moduleTitle={t('zhuke_materials.title')} />
  }

  const createProject = async () => {
    if (!courseName.trim()) {
      toast.error(t('zhuke_materials.need_course_name'))
      return
    }
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('course_name', courseName.trim())
      fd.append('mode', mode)
      fd.append('course_code', courseCode)
      fd.append('credits', credits)
      fd.append('total_hours', totalHours)
      fd.append('theory_hours', theoryHours)
      fd.append('lab_hours', labHours)
      fd.append('notes', notes)
      if (files) {
        Array.from(files).forEach((f) => fd.append('files', f))
      }
      const res = await api.post<Project>('/api/v1/zhuke-materials/projects', fd)
      setProject(res.data)
      setStep(1)
      toast.success(t('zhuke_materials.created'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  const runSyllabus = async () => {
    if (!project) return
    setBusy(true)
    try {
      const res = await api.post<Project>(`/api/v1/zhuke-materials/projects/${project.id}/syllabus`)
      setProject(res.data)
      setStep(2)
      toast.success(t('zhuke_materials.syllabus_ok'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  const runSchedule = async () => {
    if (!project) return
    if (periodEnd < periodStart) {
      toast.error(t('zhuke_materials.bad_period'))
      return
    }
    setBusy(true)
    try {
      const res = await api.post<Project>(`/api/v1/zhuke-materials/projects/${project.id}/schedule`, {
        weekday,
        period_start: periodStart,
        period_end: periodEnd,
        classroom,
        teacher,
        class_name: className,
      })
      setProject(res.data)
      setStep(3)
      toast.success(t('zhuke_materials.schedule_ok'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  const runCalendar = async () => {
    if (!project) return
    setBusy(true)
    try {
      const res = await api.post<Project>(`/api/v1/zhuke-materials/projects/${project.id}/calendar`)
      setProject(res.data)
      setStep(4)
      toast.success(t('zhuke_materials.calendar_ok'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  const runLessons = async () => {
    if (!project) return
    setBusy(true)
    try {
      const res = await api.post<Project>(`/api/v1/zhuke-materials/projects/${project.id}/lessons`)
      setProject(res.data)
      setStep(5)
      toast.success(t('zhuke_materials.lessons_ok'))
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  const runDeriveAssets = async () => {
    if (!project) return
    setBusy(true)
    try {
      const res = await api.post<Project>(`/api/v1/zhuke-materials/projects/${project.id}/derive-assets`)
      setProject(res.data)
      const id = res.data.id
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 2000))
        const { data: p } = await api.get<Project>(`/api/v1/zhuke-materials/projects/${id}`)
        setProject(p)
        if (p.status === 'assets_done') {
          toast.success(t('zhuke_materials.derive_ok'))
          break
        }
        if (p.status === 'assets_failed') {
          toast.error(p.error || t('zhuke_materials.err_derive'))
          break
        }
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke_materials.err_derive'))
    } finally {
      setBusy(false)
    }
  }

  const download = async () => {
    if (!project) return
    setBusy(true)
    try {
      const res = await api.get(`/api/v1/zhuke-materials/projects/${project.id}/download`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `珠科材料_${project.course_name || project.id.slice(0, 8)}.zip`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(t('zhuke_materials.download_ok'))
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : t('zhuke_materials.fail'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600 inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('tools.dashboard')}
          </Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('zhuke_materials.title')}</span>
        </div>

        <div className="flex items-start gap-3 mb-6">
          <div className="w-11 h-11 rounded-xl bg-sky-50 flex items-center justify-center shrink-0">
            <BookOpen className="w-6 h-6 text-sky-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('zhuke_materials.title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('zhuke_materials.subtitle')}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          {steps.map((label, i) => (
            <div
              key={label}
              className={`text-xs px-2.5 py-1 rounded-full border ${
                i === step
                  ? 'bg-sky-600 text-white border-sky-600'
                  : i < step
                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                    : 'bg-white text-gray-400 border-gray-200'
              }`}
            >
              {i + 1}. {label}
            </div>
          ))}
        </div>

        <Card className="p-6 space-y-4">
          {step === 0 && (
            <>
              <p className="text-sm text-gray-600">{t('zhuke_materials.upload_hint')}</p>
              <label className="block text-sm font-medium text-gray-700">
                {t('zhuke_materials.course_name')}
                <input
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  value={courseName}
                  onChange={(e) => setCourseName(e.target.value)}
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.course_code')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} />
                </label>
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.mode')}
                  <select className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={mode} onChange={(e) => setMode(e.target.value)}>
                    <option value="C">C — {t('zhuke_materials.mode_c')}</option>
                    <option value="B">B — {t('zhuke_materials.mode_b')}</option>
                    <option value="A">A — {t('zhuke_materials.mode_a')}</option>
                  </select>
                </label>
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.credits')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={credits} onChange={(e) => setCredits(e.target.value)} />
                </label>
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.total_hours')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={totalHours} onChange={(e) => setTotalHours(e.target.value)} />
                </label>
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.theory_hours')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={theoryHours} onChange={(e) => setTheoryHours(e.target.value)} />
                </label>
                <label className="block text-sm text-gray-700">
                  {t('zhuke_materials.lab_hours')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={labHours} onChange={(e) => setLabHours(e.target.value)} />
                </label>
              </div>
              <label className="block text-sm text-gray-700">
                {t('zhuke_materials.notes')}
                <textarea className="mt-1 w-full rounded-lg border px-3 py-2 text-sm min-h-[72px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <Upload className="w-4 h-4" />
                {t('zhuke_materials.upload_files')}
                <input type="file" multiple className="text-xs" onChange={(e) => setFiles(e.target.files)} />
              </label>
              <Button onClick={createProject} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('zhuke_materials.next')}
              </Button>
            </>
          )}

          {step === 1 && project && (
            <>
              <p className="text-sm text-gray-600">{t('zhuke_materials.syllabus_hint')}</p>
              <p className="text-xs text-gray-400">ID: {project.id} · mode {project.mode}</p>
              <Button onClick={runSyllabus} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('zhuke_materials.gen_syllabus')}
              </Button>
            </>
          )}

          {step === 2 && project && (
            <>
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {t('zhuke_materials.schedule_gate')}
              </p>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  {t('zhuke_materials.weekday')}
                  <select className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={weekday} onChange={(e) => setWeekday(e.target.value)}>
                    {WEEKDAYS.map((w) => (
                      <option key={w} value={w}>{w}</option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  {t('zhuke_materials.classroom')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={classroom} onChange={(e) => setClassroom(e.target.value)} />
                </label>
                <label className="block text-sm">
                  {t('zhuke_materials.period_start')}
                  <input type="number" min={1} max={12} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={periodStart} onChange={(e) => setPeriodStart(Number(e.target.value))} />
                </label>
                <label className="block text-sm">
                  {t('zhuke_materials.period_end')}
                  <input type="number" min={1} max={12} className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={periodEnd} onChange={(e) => setPeriodEnd(Number(e.target.value))} />
                </label>
                <label className="block text-sm">
                  {t('zhuke_materials.teacher')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={teacher} onChange={(e) => setTeacher(e.target.value)} />
                </label>
                <label className="block text-sm">
                  {t('zhuke_materials.class_name')}
                  <input className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" value={className} onChange={(e) => setClassName(e.target.value)} />
                </label>
              </div>
              <Button onClick={runSchedule} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('zhuke_materials.confirm_schedule')}
              </Button>
            </>
          )}

          {step === 3 && project && (
            <>
              <p className="text-sm text-gray-600">{t('zhuke_materials.calendar_hint')}</p>
              <Button onClick={runCalendar} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('zhuke_materials.gen_calendar')}
              </Button>
            </>
          )}

          {step === 4 && project && (
            <>
              <p className="text-sm text-gray-600">{t('zhuke_materials.lessons_hint')}</p>
              <Button onClick={runLessons} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {t('zhuke_materials.gen_lessons')}
              </Button>
            </>
          )}

          {step === 5 && project && (
            <>
              <div className="flex items-center gap-2 text-green-700 text-sm">
                <CheckCircle2 className="w-5 h-5" />
                {t('zhuke_materials.ready')}
              </div>
              <ul className="text-sm text-gray-600 list-disc pl-5 space-y-1">
                {project.has_syllabus_file && <li>{t('zhuke_materials.file_syllabus')}</li>}
                {project.has_calendar_theory && <li>{t('zhuke_materials.file_calendar_theory')}</li>}
                {project.has_calendar_lab && <li>{t('zhuke_materials.file_calendar_lab')}</li>}
                {project.has_lessons_file && <li>{t('zhuke_materials.file_lessons')}</li>}
                {project.has_material_html && <li>{t('zhuke_materials.file_material')}</li>}
                {project.has_ppt && <li>{t('zhuke_materials.file_ppt')}</li>}
              </ul>
              {project.status === 'assets_running' && (
                <p className="text-sm text-sky-700 bg-sky-50 border border-sky-200 rounded-lg px-3 py-2">
                  {t('zhuke_materials.derive_hint')}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={runDeriveAssets}
                  disabled={
                    busy ||
                    project.status === 'assets_running' ||
                    !project.has_syllabus_file ||
                    !project.has_lessons_file
                  }
                >
                  {busy || project.status === 'assets_running' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : null}
                  {project.status === 'assets_running'
                    ? t('zhuke_materials.btn_derive_running')
                    : t('zhuke_materials.btn_derive_assets')}
                </Button>
                <Button onClick={download} disabled={busy || project.status === 'assets_running'}>
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  {t('zhuke_materials.download')}
                </Button>
              </div>
              {(project.has_material_html || project.has_ppt) && (
                <p className="text-xs text-gray-500">{t('zhuke_materials.derive_zip_tip')}</p>
              )}
            </>
          )}
        </Card>
      </main>
    </div>
  )
}
