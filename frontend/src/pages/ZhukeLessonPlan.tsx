import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useT } from '../i18n/translations'
import { toast } from '../components/ui/Toast'
import { api, ZHUKE_API_TIMEOUT_MS, ZHUKE_LIST_TIMEOUT_MS, ZHUKE_WRITE_TIMEOUT_MS } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { hasCapability } from '../lib/access'
import { readApiErrorDetail } from '../lib/blobError'
import LockedComingSoon from '../components/semester/LockedComingSoon'
import { getSocket, joinUser } from '../services/socket'
import { clearZhukeRecoverSession, postZhukeCancel, postZhukeRegenerate, useZhukeAutoRecover, fetchZhukeStatus, handleZhuke409, isZhuke409 } from '../hooks/useZhukeRecover'
import {
  ArrowLeft,
  Upload,
  GraduationCap,
  Loader2,
  Download,
  Sparkles,
  Square,
  Play,
  Trash2,
  FileText,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'

type LessonRow = {
  lesson_no?: string
  title?: string
  week?: string
  weekday?: string
  periods?: string
  date?: string
  content?: string
  hours?: string
  time_label?: string
}

type ParseResp = {
  file_name: string
  ext: string
  cover: {
    college?: string
    course_name?: string
    course_type?: string
    teacher?: string
    class_name?: string
  }
  lessons: LessonRow[]
  raw_preview: string[][]
}

type GenerateResp = {
  result_id: string
  file_name: string
  file_size?: number
  lessons_count: number
  expires_at: string
}

type PreviewLesson = {
  lesson_idx: number
  title: string
  time_label: string
  hours: string
  sections: Record<string, string>
  failed: boolean
}

type StatusResp = {
  result_id: string
  status: 'queued' | 'running' | 'done' | 'failed' | 'unknown'
  done: number
  total: number
  failures: number
  file_name?: string
  error?: string
  file_exists?: boolean
  recovering?: boolean
  recover_action?: string | null
  stalled_reason?: 'queued_timeout' | 'no_progress' | null
  lessons?: PreviewLesson[]
}

type Phase = 'idle' | 'queued' | 'running' | 'done' | 'failed' | 'cancelled'

type HistoryItem = {
  result_id: string
  record_id: string
  course_name: string
  file_name: string
  lessons_count: number
  failures_count: number
  status: 'queued' | 'running' | 'done' | 'failed' | string
  file_size: number
  created_at: string
  file_exists?: boolean
  recovering?: boolean
  recover_action?: string | null
}

const LS_ACTIVE_RID_KEY = 'zhuke_active_result_id'

const MAJOR_PRESETS = ['数据科学与大数据技术', '应用统计', '数据计算']

export default function ZhukeLessonPlan() {
  const t = useT()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const allowed = hasCapability(user as any, 'can_semester_helper')

  const [file, setFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parsed, setParsed] = useState<ParseResp | null>(null)

  const [cover, setCover] = useState({
    college: '',
    course_name: '',
    course_type: '',
    teacher: '',
    class_name: '',
  })
  const [majorPreset, setMajorPreset] = useState<string>(MAJOR_PRESETS[0])
  const [majorCustom, setMajorCustom] = useState('')
  const [semesterLabel, setSemesterLabel] = useState('2025～2026 学年第 2 学期')

  const [lessons, setLessons] = useState<LessonRow[]>([])

  // Shared "lesson time" defaults — used to bulk-fill week / weekday / periods
  // for every lesson. Schedule files (教学日历) typically don't carry 节次, so
  // the user must supply it here; week defaults to lesson_no, weekday defaults
  // to the parsed value of the first lesson.
  const [defaultWeekStart, setDefaultWeekStart] = useState<number>(1)
  const [defaultWeekday, setDefaultWeekday] = useState<string>('')
  const [defaultPeriods, setDefaultPeriods] = useState<string>('')

  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState<GenerateResp | null>(null)
  const [backendReady, setBackendReady] = useState<boolean | null>(null)
  const [skipAi, setSkipAi] = useState(false)
  const [downloading, setDownloading] = useState<'docx' | 'pdf' | ''>('')
  const [stopping, setStopping] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  // Background-job state — drives the progress bar in step 4 and gates the
  // download buttons until the worker fires zhuke_complete (or status poll
  // sees status='done').
  const [phase, setPhase] = useState<Phase>('idle')
  const [progress, setProgress] = useState<{ done: number; total: number; failures: number }>({
    done: 0,
    total: 0,
    failures: 0,
  })
  const [failureNote, setFailureNote] = useState<string>('')
  const activeResultId = useRef<string | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])

  // Live-preview state: per-lesson sections streamed from the worker via
  // socket.io `zhuke_lesson_done`. Keyed by lesson_idx so out-of-order arrival
  // (which happens with concurrent Kimi calls) doesn't corrupt the list.
  // `currentLesson*` are the heartbeat indicators driven by
  // `zhuke_lesson_started`. `startedAt` powers the ETA calculation.
  const [previewLessons, setPreviewLessons] = useState<Record<number, PreviewLesson>>({})
  const [currentLessonIdx, setCurrentLessonIdx] = useState<number | null>(null)
  const [currentLessonTitle, setCurrentLessonTitle] = useState<string>('')
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [stalledReason, setStalledReason] = useState<'queued_timeout' | 'no_progress' | null>(null)
  // 本地"无进展"watcher：每次 progress.done 变化重置时间戳；若 phase==='running'
  // 且 done 5 分钟未推进 → 显示 stalled 提示。补足后端 stalled_reason 只在
  // done === 0 时上报的情况（reload 卡在 5/16 这种就被这条本地 watcher 兜住）。
  const lastProgressRef = useRef<{ done: number; at: number }>({ done: 0, at: Date.now() })
  const [fileReady, setFileReady] = useState(false)
  const [recoverRid, setRecoverRid] = useState<string | null>(null)
  const [recoverAutoPost, setRecoverAutoPost] = useState(false)

  const clearRecoverState = () => {
    setRecoverRid(null)
    setRecoverAutoPost(false)
  }

  const { recovering: autoRecovering } = useZhukeAutoRecover({
    resultId: recoverRid,
    enabled: !!recoverRid,
    autoPostRecover: recoverAutoPost,
    t,
    onImpossible: clearRecoverState,
    onStalled: clearRecoverState,
    onStatus: (s) => {
      if (s.total > 0) {
        setProgress({ done: s.done, total: s.total, failures: s.failures })
      }
      if (s.status === 'running' || s.status === 'queued') {
        setPhase(s.status as Phase)
      }
      if (Array.isArray(s.lessons) && s.lessons.length > 0) {
        setPreviewLessons((prev) => {
          const next = { ...prev }
          for (const l of s.lessons || []) {
            if (typeof l?.lesson_idx === 'number') {
              next[l.lesson_idx] = {
                lesson_idx: l.lesson_idx,
                title: l.title || '',
                time_label: l.time_label || '',
                hours: l.hours || '',
                sections: l.sections || {},
                failed: !!l.failed,
              }
            }
          }
          return next
        })
      }
    },
    onComplete: () => {
      setFileReady(true)
      setPhase('done')
      clearRecoverState()
      try {
        localStorage.removeItem(LS_ACTIVE_RID_KEY)
      } catch {
        /* ignore */
      }
      void reloadHistory()
      toast.success(t('zhuke.generate_complete').replace('{n}', String(progress.total)).replace('{f}', '0'))
    },
  })

  // Refresh the recent-generations card by re-querying /zhuke/history.
  const reloadHistory = async () => {
    try {
      const res = await api.get<HistoryItem[]>(
        '/api/v1/semester-helper/zhuke/history?limit=10',
        { timeout: ZHUKE_LIST_TIMEOUT_MS },
      )
      setHistory(Array.isArray(res.data) ? res.data : [])
    } catch {
      // silent — empty history is the safe fallback
    }
  }

  const major = majorPreset === '其他' ? majorCustom.trim() : majorPreset

  if (!allowed) {
    return <LockedComingSoon moduleTitle={t('zhuke.title')} />
  }

  const handleFile = (f: File | null) => {
    setFile(f)
    setParsed(null)
    setGenerated(null)
  }

  const doParse = async () => {
    if (!file) return
    setParsing(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post<ParseResp>('/api/v1/semester-helper/zhuke/parse-schedule', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: ZHUKE_WRITE_TIMEOUT_MS,
      })
      const data = res.data
      setParsed(data)
      setCover({
        college: data.cover?.college || '',
        course_name: data.cover?.course_name || '',
        course_type: data.cover?.course_type || '',
        teacher: data.cover?.teacher || '',
        class_name: data.cover?.class_name || '',
      })
      // Auto-fill `week` with the lesson serial number when the schedule
      // didn't carry a 周次 column (the 珠科 教学日历 typically doesn't).
      setLessons((data.lessons || []).map((l, idx) => ({
        ...l,
        week: l.week || String(idx + 1),
      })))
      // Pre-fill the shared `星期` default from the first lesson's parsed
      // weekday — 珠科课程通常每周都是同一天上课。
      setDefaultWeekday(data.lessons?.[0]?.weekday || '')
      if (!data.lessons?.length) {
        toast.error(t('zhuke.parse_no_rows'))
      } else {
        toast.success(t('zhuke.parse_ok').replace('{n}', String(data.lessons.length)))
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || t('zhuke.parse_failed'))
    } finally {
      setParsing(false)
    }
  }

  const removeLesson = (idx: number) =>
    setLessons((prev) => prev.filter((_, i) => i !== idx))

  const updateLesson = (idx: number, patch: Partial<LessonRow>) =>
    setLessons((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)))

  // Apply the three shared "lesson time" defaults to every lesson row. Week is
  // an offset model (`起始周次 + idx`); weekday & periods overwrite verbatim
  // when the default field is non-empty.
  const applyDefaultsToAll = () => {
    setLessons((prev) =>
      prev.map((l, idx) => ({
        ...l,
        week: String(defaultWeekStart + idx),
        weekday: defaultWeekday || l.weekday || '',
        periods: defaultPeriods || l.periods || '',
      })),
    )
    toast.success(t('zhuke.apply_defaults_ok').replace('{n}', String(lessons.length)))
  }

  const canGenerate = useMemo(() => {
    if (backendReady === false) return false
    if (!cover.course_name.trim()) return false
    if (!lessons.length) return false
    if (majorPreset === '其他' && !majorCustom.trim()) return false
    return true
  }, [backendReady, cover.course_name, lessons.length, majorPreset, majorCustom])

  const checkBackend = async () => {
    try {
      const res = await api.get<{ ready?: boolean; db_ok?: boolean }>(
        '/api/v1/semester-helper/ping',
        { timeout: ZHUKE_LIST_TIMEOUT_MS },
      )
      const ok = res.data?.ready !== false && res.data?.db_ok !== false
      setBackendReady(ok)
      return ok
    } catch {
      setBackendReady(false)
      return false
    }
  }

  const doGenerate = async () => {
    if (!canGenerate) return
    if (backendReady === false) {
      toast.error(t('zhuke.backend_unreachable'))
      return
    }
    if (backendReady === null) {
      const ok = await checkBackend()
      if (!ok) {
        toast.error(t('zhuke.backend_unreachable'))
        return
      }
    }
    setGenerating(true)
    setGenerated(null)
    setFailureNote('')
    setProgress({ done: 0, total: lessons.length, failures: 0 })
    setPhase('queued')
    setFileReady(false)
    // Reset live preview for the new run — the previous one's cards would
    // confuse the user if they stayed visible alongside the new heartbeat.
    setPreviewLessons({})
    setCurrentLessonIdx(null)
    setCurrentLessonTitle('')
    setStartedAt(Date.now())
    setStalledReason(null)
    try {
      const res = await api.post<GenerateResp>('/api/v1/semester-helper/zhuke/generate', {
        cover,
        lessons,
        major,
        semester_label: semesterLabel,
        skip_ai: skipAi,
      }, { timeout: ZHUKE_WRITE_TIMEOUT_MS })
      const data = res.data
      activeResultId.current = data.result_id
      try {
        localStorage.setItem(LS_ACTIVE_RID_KEY, data.result_id)
      } catch {
        /* localStorage可能在隐身模式禁用，忽略 */
      }
      setGenerated(data)
      setProgress({ done: 0, total: data.lessons_count, failures: 0 })
      toast.success(t('zhuke.generate_started').replace('{n}', String(data.lessons_count)))
      // refresh history card so the queued row shows up immediately
      void reloadHistory()
    } catch (e: unknown) {
      activeResultId.current = null
      try {
        localStorage.removeItem(LS_ACTIVE_RID_KEY)
      } catch {
        /* ignore */
      }
      const status = (e as { response?: { status?: number } })?.response?.status
      const detail = await handleZhuke409(e, t, 'zhuke.generate_failed')
      if (status === 409) {
        setPhase('idle')
        setFailureNote('')
      } else {
        setPhase('failed')
        setFailureNote(detail)
      }
      toast.error(detail)
    } finally {
      setGenerating(false)
    }
  }

  const doStop = async () => {
    const rid = activeResultId.current || generated?.result_id || recoverRid
    if (!rid) return
    if (!window.confirm(
      phase === 'queued' || phase === 'running'
        ? t('zhuke.stop_generate_confirm')
        : t('zhuke.stop_confirm'),
    )) return
    setStopping(true)
    try {
      const res = await postZhukeCancel(rid)
      clearZhukeRecoverSession(rid)
      clearRecoverState()
      activeResultId.current = null
      try {
        localStorage.removeItem(LS_ACTIVE_RID_KEY)
      } catch {
        /* ignore */
      }
      if (res.file_exists) {
        setPhase('done')
        setFileReady(true)
      } else {
        setPhase('cancelled')
        setFailureNote(res.message || t('zhuke.cancelled_by_user'))
      }
      toast.success(res.message || t('zhuke.stop_success'))
      void reloadHistory()
    } catch (e: unknown) {
      if (isZhuke409(e)) {
        setPhase('idle')
        setFailureNote('')
      }
      toast.error(await handleZhuke409(e, t, 'zhuke.stop_failed'))
    } finally {
      setStopping(false)
    }
  }

  const doRetryFailed = async () => {
    const rid = activeResultId.current || generated?.result_id || recoverRid
    if (!rid || progress.failures <= 0) return
    if (!window.confirm(t('zhuke.retry_failed_confirm'))) return
    setRegenerating(true)
    try {
      const res = await postZhukeRegenerate(rid)
      if (res.action === 'impossible') {
        toast.error(t('zhuke.need_reupload'))
        return
      }
      activeResultId.current = rid
      setFileReady(false)
      setStartedAt(Date.now())
      setPhase(res.status === 'queued' ? 'queued' : 'running')
      toast.success(res.message || t('zhuke.regenerate_started'))
      void reloadHistory()
    } catch (e: unknown) {
      toast.error(await handleZhuke409(e, t, 'zhuke.recover_impossible'))
    } finally {
      setRegenerating(false)
    }
  }

  const doRegenerate = async () => {
    const rid = activeResultId.current || generated?.result_id || recoverRid
    if (!rid) return
    if (!window.confirm(t('zhuke.regenerate_confirm'))) return
    setRegenerating(true)
    try {
      const res = await postZhukeRegenerate(rid)
      if (res.action === 'impossible') {
        toast.error(t('zhuke.need_reupload'))
        setPhase('failed')
        setFailureNote(t('zhuke.need_reupload'))
        return
      }
      activeResultId.current = rid
      setFileReady(false)
      setStartedAt(Date.now())
      if (res.status === 'queued' || res.status === 'running' || res.recovering) {
        setPhase(res.status === 'queued' ? 'queued' : 'running')
        toast.success(res.message || t('zhuke.regenerate_started'))
      } else if (res.file_exists) {
        setPhase('done')
        setFileReady(true)
        toast.success(res.message || t('zhuke.generate_ok'))
      } else {
        setPhase('running')
        toast.info(res.message || t('zhuke.auto_recovering'))
      }
      void reloadHistory()
    } catch (e: unknown) {
      toast.error(await handleZhuke409(e, t, 'zhuke.recover_impossible'))
    } finally {
      setRegenerating(false)
    }
  }

  // Download by an explicit result_id (used by the history card).
  const doDownloadById = async (rid: string, fmt: 'docx' | 'pdf', filename: string) => {
    if (!rid) return
    setDownloading(fmt)
    try {
      const res = await api.get(
        `/api/v1/semester-helper/zhuke/${encodeURIComponent(rid)}/download`,
        { params: { format: fmt }, responseType: 'blob', timeout: ZHUKE_WRITE_TIMEOUT_MS },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = fmt === 'pdf' ? filename.replace(/\.docx$/i, '.pdf') : filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      toast.error(await handleZhuke409(e, t, 'zhuke.download_failed'))
    } finally {
      setDownloading('')
    }
  }

  // ── On mount: backend ping + load history + resume in-progress generation
  useEffect(() => {
    void checkBackend()
    void reloadHistory()
    let rid: string | null = null
    try {
      rid = localStorage.getItem(LS_ACTIVE_RID_KEY)
    } catch {
      rid = null
    }
    if (!rid) return
    ;(async () => {
      try {
        const s = await fetchZhukeStatus(rid!, { light: true })
        // Seed preview cards from server-side sidecar so the UI rebuilds
        // every already-generated lesson immediately on refresh; new socket
        // events (if any) merge in on top of this.
        const seedPreview: Record<number, PreviewLesson> = {}
        for (const l of s.lessons || []) {
          if (typeof l?.lesson_idx === 'number') {
            seedPreview[l.lesson_idx] = {
              lesson_idx: l.lesson_idx,
              title: l.title || '',
              time_label: l.time_label || '',
              hours: l.hours || '',
              sections: l.sections || {},
              failed: !!l.failed,
            }
          }
        }
        if (s.status === 'failed' && !s.recovering) {
          try {
            localStorage.removeItem(LS_ACTIVE_RID_KEY)
          } catch {
            /* ignore */
          }
          return
        }
        if (s.status === 'done') {
          const ready = s.file_exists !== false && !s.recovering
          activeResultId.current = rid
          setGenerated({
            result_id: rid as string,
            file_name: s.file_name || 'lesson.docx',
            lessons_count: s.total || s.done || 0,
            expires_at: '',
          })
          setProgress({ done: s.done, total: s.total, failures: s.failures })
          setPreviewLessons(seedPreview)
          if (ready) {
            setFileReady(true)
            setPhase('done')
            try {
              localStorage.removeItem(LS_ACTIVE_RID_KEY)
            } catch {
              /* ignore */
            }
            toast.success(t('zhuke.history_resumed'))
          } else if (s.recovering) {
            setFileReady(false)
            setPhase('running')
            setStartedAt(Date.now())
            setRecoverRid(rid)
            setRecoverAutoPost(true)
            toast.info(t('zhuke.auto_recovering'))
          } else {
            setFileReady(false)
            setPhase('done')
            clearRecoverState()
          }
        } else if (s.status === 'queued' || s.status === 'running') {
          activeResultId.current = rid
          setGenerated({
            result_id: rid as string,
            file_name: s.file_name || '',
            lessons_count: s.total || 0,
            expires_at: '',
          })
          setProgress({ done: s.done, total: s.total, failures: s.failures })
          setPhase(s.status as Phase)
          setPreviewLessons(seedPreview)
          setStartedAt((prev) => prev ?? Date.now())
          toast.success(t('zhuke.history_resumed'))
        } else {
          // unknown / stale / idle → clean up so we don't get stuck retrying.
          try {
            localStorage.removeItem(LS_ACTIVE_RID_KEY)
          } catch {
            /* ignore */
          }
        }
      } catch {
        try {
          localStorage.removeItem(LS_ACTIVE_RID_KEY)
        } catch {
          /* ignore */
        }
      }
    })()
    // run once on mount only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Socket.IO subscription: zhuke_progress / zhuke_complete / zhuke_failed
  //    + 10 s status-poll fallback in case socket events are dropped during a
  //    reconnect window (uvicorn hot-reload, etc.).
  useEffect(() => {
    if (!user?.id) return
    const socket = getSocket()
    joinUser(String(user.id))

    const onProgress = (data: any) => {
      if (!activeResultId.current || data?.result_id !== activeResultId.current) return
      setPhase('running')
      setProgress({
        done: Number(data.done || 0),
        total: Number(data.total || 0),
        failures: Number(data.failures || 0),
      })
    }
    const onLessonStarted = (data: any) => {
      if (!activeResultId.current || data?.result_id !== activeResultId.current) return
      // Heartbeat — drives the "正在生成第 N 节" line and starts a timer if
      // we haven't seen one yet (covers resume case where doGenerate didn't
      // run in this session).
      setCurrentLessonIdx(Number(data.lesson_idx))
      setCurrentLessonTitle(String(data.lesson_title || ''))
      setPhase('running')
      setStartedAt((prev) => prev ?? Date.now())
    }
    const onLessonDone = (data: any) => {
      if (!activeResultId.current || data?.result_id !== activeResultId.current) return
      const idx = Number(data.lesson_idx)
      if (Number.isNaN(idx)) return
      setPreviewLessons((prev) => ({
        ...prev,
        [idx]: {
          lesson_idx: idx,
          title: String(data.lesson_title || ''),
          time_label: String(data.time_label || ''),
          hours: String(data.hours || ''),
          sections: (data.sections || {}) as Record<string, string>,
          failed: !!data.failed,
        },
      }))
    }
    const onComplete = (data: any) => {
      if (!activeResultId.current || data?.result_id !== activeResultId.current) return
      setPhase('done')
      setFileReady(true)
      setProgress((p) => ({
        done: Number(data.lessons_count || p.done),
        total: Number(data.lessons_count || p.total),
        failures: Number(data.failures_count || p.failures),
      }))
      try {
        localStorage.removeItem(LS_ACTIVE_RID_KEY)
      } catch {
        /* ignore */
      }
      const fails = Number(data.failures_count || 0)
      toast.success(
        t('zhuke.generate_complete')
          .replace('{n}', String(data.lessons_count))
          .replace('{f}', String(fails)),
      )
      void reloadHistory()
    }
    const onFailed = (data: any) => {
      if (!activeResultId.current || data?.result_id !== activeResultId.current) return
      setPhase('failed')
      setFailureNote(String(data.error || t('zhuke.generate_failed')))
      try {
        localStorage.removeItem(LS_ACTIVE_RID_KEY)
      } catch {
        /* ignore */
      }
      toast.error(String(data.error || t('zhuke.generate_failed')))
      void reloadHistory()
    }

    socket.on('zhuke_progress', onProgress)
    socket.on('zhuke_lesson_started', onLessonStarted)
    socket.on('zhuke_lesson_done', onLessonDone)
    socket.on('zhuke_complete', onComplete)
    socket.on('zhuke_failed', onFailed)
    return () => {
      socket.off('zhuke_progress', onProgress)
      socket.off('zhuke_lesson_started', onLessonStarted)
      socket.off('zhuke_lesson_done', onLessonDone)
      socket.off('zhuke_complete', onComplete)
      socket.off('zhuke_failed', onFailed)
    }
  }, [user?.id, t])

  // Fallback status poll — every 5 s while phase is queued/running.
  useEffect(() => {
    if (phase !== 'queued' && phase !== 'running') return
    if (!activeResultId.current) return
    let cancelled = false
    const tick = async () => {
      const rid = activeResultId.current
      if (!rid) return
      try {
        const s = await fetchZhukeStatus(rid, { light: true })
        if (cancelled || activeResultId.current !== rid) return
        if (s.total > 0) {
          setProgress({ done: s.done, total: s.total, failures: s.failures })
        }
        if (s.stalled_reason) {
          setStalledReason(s.stalled_reason)
        } else if (startedAt) {
          const elapsed = Date.now() - startedAt
          if (s.status === 'queued' && s.done === 0 && elapsed > 90_000) {
            setStalledReason('queued_timeout')
          } else if (s.status === 'running' && s.done === 0 && elapsed > 240_000) {
            setStalledReason('no_progress')
          } else {
            setStalledReason(null)
          }
        }
        if (Array.isArray(s.lessons) && s.lessons.length > 0) {
          setPreviewLessons((prev) => {
            const next = { ...prev }
            for (const l of s.lessons || []) {
              if (typeof l?.lesson_idx === 'number') {
                next[l.lesson_idx] = {
                  lesson_idx: l.lesson_idx,
                  title: l.title || '',
                  time_label: l.time_label || '',
                  hours: l.hours || '',
                  sections: l.sections || {},
                  failed: !!l.failed,
                }
              }
            }
            return next
          })
          const idxs = (s.lessons || [])
            .map((l) => l.lesson_idx)
            .filter((n): n is number => typeof n === 'number')
          if (idxs.length > 0 && s.status === 'running') {
            const nextIdx = Math.max(...idxs) + 1
            const cap = s.total > 0 ? s.total - 1 : nextIdx
            const hintIdx = Math.min(nextIdx, cap)
            setCurrentLessonIdx((prev) => prev ?? hintIdx)
            const hintLesson = (s.lessons || []).find((l) => l.lesson_idx === hintIdx)
            if (hintLesson?.title) {
              setCurrentLessonTitle((prev) => prev || hintLesson.title || '')
            }
            setStartedAt((prev) => prev ?? Date.now())
          }
        }
        if (s.status === 'cancelled' || s.recover_action === 'cancelled') {
          setPhase('cancelled')
          setStalledReason(null)
          clearRecoverState()
          activeResultId.current = null
          try {
            localStorage.removeItem(LS_ACTIVE_RID_KEY)
          } catch {
            /* ignore */
          }
          setFailureNote(t('zhuke.cancelled_by_user'))
          void reloadHistory()
          return
        }
        if (s.status === 'running') setPhase('running')
        else if (s.status === 'queued') setPhase('queued')
        else if (s.status === 'done') {
          const ready = s.file_exists !== false && !s.recovering
          if (!ready && s.recovering) {
            setRecoverRid(rid)
            setRecoverAutoPost(true)
            setPhase('running')
          } else if (ready) {
            setFileReady(true)
            setPhase('done')
            clearRecoverState()
            setStalledReason(null)
            try {
              localStorage.removeItem(LS_ACTIVE_RID_KEY)
            } catch {
              /* ignore */
            }
            toast.success(
              t('zhuke.generate_complete')
                .replace('{n}', String(s.total || progress.total))
                .replace('{f}', String(s.failures)),
            )
            void reloadHistory()
          }
        } else if (s.status === 'failed') {
          if (s.recovering) {
            setRecoverRid(rid)
            setPhase('running')
          } else {
            setPhase('failed')
            setStalledReason(null)
            try {
              localStorage.removeItem(LS_ACTIVE_RID_KEY)
            } catch {
              /* ignore */
            }
            setFailureNote(s.error || t('zhuke.generate_failed'))
            void reloadHistory()
          }
        }
      } catch {
        // silent — next tick will retry
      }
    }
    const handle = setInterval(tick, 8000)
    void tick()
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [phase, t, progress.total, recoverRid, startedAt])

  // Local stuck-watcher: if running but progress.done has not advanced in
  // 5 min, surface stalled_reason='no_progress' so the UI offers a regen
  // button. Complements the server-side stalled detector which only fires
  // when done === 0.
  useEffect(() => {
    if (phase !== 'queued' && phase !== 'running') {
      lastProgressRef.current = { done: progress.done, at: Date.now() }
      return
    }
    if (progress.done !== lastProgressRef.current.done) {
      lastProgressRef.current = { done: progress.done, at: Date.now() }
      return
    }
    const tick = () => {
      if (phase !== 'queued' && phase !== 'running') return
      const stuckMs = Date.now() - lastProgressRef.current.at
      if (stuckMs > 5 * 60_000) {
        setStalledReason((prev) => prev ?? 'no_progress')
      }
    }
    const handle = setInterval(tick, 15_000)
    return () => clearInterval(handle)
  }, [phase, progress.done])

  const doDownload = async (fmt: 'docx' | 'pdf') => {
    if (!generated) return
    setDownloading(fmt)
    try {
      const res = await api.get(
        `/api/v1/semester-helper/zhuke/${encodeURIComponent(generated.result_id)}/download`,
        { params: { format: fmt }, responseType: 'blob', timeout: ZHUKE_WRITE_TIMEOUT_MS },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = fmt === 'pdf'
        ? generated.file_name.replace(/\.docx$/i, '.pdf')
        : generated.file_name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      toast.error(await handleZhuke409(e, t, 'zhuke.download_failed'))
    } finally {
      setDownloading('')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
          <Link to="/dashboard" className="hover:text-brand-600 inline-flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('zhuke.back_dashboard')}
          </Link>
          <span>/</span>
          <Link to="/semester-helper" className="hover:text-brand-600">{t('semester_helper.title')}</Link>
          <span>/</span>
          <span className="text-gray-900 font-medium">{t('zhuke.title')}</span>
        </div>

        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center shrink-0">
            <GraduationCap className="w-5 h-5 text-brand-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{t('zhuke.title')}</h1>
        </div>
        <p className="text-sm text-gray-500 mb-6">{t('zhuke.subtitle')}</p>

        {/* Step 1 — Upload */}
        <Card className="mb-5">
          <h2 className="text-base font-semibold text-gray-900 mb-3">
            {t('zhuke.step1_title')}
          </h2>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-gray-300 cursor-pointer hover:border-brand-400 transition">
              <Upload className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-700">{file ? file.name : t('zhuke.step1_pick')}</span>
              <input
                type="file"
                accept=".xlsx,.xlsm,.xls,.docx,.doc,.pdf"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0] || null)}
              />
            </label>
            <Button onClick={doParse} disabled={!file || parsing} size="sm">
              {parsing ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
              {t('zhuke.step1_parse')}
            </Button>
            {parsed && (
              <span className="text-xs text-green-600 inline-flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {t('zhuke.parse_ok').replace('{n}', String(parsed.lessons.length))}
              </span>
            )}
          </div>
          {parsed?.raw_preview && parsed.raw_preview.length > 0 && (
            <details className="mt-3 text-xs text-gray-600">
              <summary className="cursor-pointer">{t('zhuke.preview_toggle')}</summary>
              <div className="mt-2 overflow-x-auto">
                <table className="text-xs border border-gray-200">
                  <tbody>
                    {parsed.raw_preview.map((row, ri) => (
                      <tr key={ri} className={ri === 0 ? 'bg-gray-100 font-medium' : ''}>
                        {row.map((c, ci) => (
                          <td key={ci} className="border border-gray-200 px-2 py-1 max-w-[180px] truncate">{c}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </Card>

        {/* Step 2 — Cover */}
        <Card className="mb-5">
          <h2 className="text-base font-semibold text-gray-900 mb-3">{t('zhuke.step2_title')}</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label={t('zhuke.field_college')} value={cover.college} onChange={(v) => setCover((c) => ({ ...c, college: v }))} />
            <Field label={t('zhuke.field_course_name')} value={cover.course_name} onChange={(v) => setCover((c) => ({ ...c, course_name: v }))} required />
            <Field label={t('zhuke.field_class_name')} value={cover.class_name} onChange={(v) => setCover((c) => ({ ...c, class_name: v }))} />
            <Field label={t('zhuke.field_course_type')} value={cover.course_type} onChange={(v) => setCover((c) => ({ ...c, course_type: v }))} />
            <Field label={t('zhuke.field_teacher')} value={cover.teacher} onChange={(v) => setCover((c) => ({ ...c, teacher: v }))} />
            <div>
              <label className="block text-xs text-gray-600 mb-1">{t('zhuke.field_major')}<span className="text-red-500">*</span></label>
              <div className="flex gap-2">
                <select
                  value={majorPreset}
                  onChange={(e) => setMajorPreset(e.target.value)}
                  className="flex-1 px-2 py-1.5 rounded border border-gray-300 text-sm"
                >
                  {MAJOR_PRESETS.map((m) => <option key={m} value={m}>{m}</option>)}
                  <option value="其他">{t('zhuke.major_other')}</option>
                </select>
                {majorPreset === '其他' && (
                  <input
                    value={majorCustom}
                    onChange={(e) => setMajorCustom(e.target.value)}
                    placeholder={t('zhuke.major_other_placeholder')}
                    className="flex-1 px-2 py-1.5 rounded border border-gray-300 text-sm"
                  />
                )}
              </div>
            </div>
            <Field label={t('zhuke.field_semester')} value={semesterLabel} onChange={setSemesterLabel} />
          </div>
        </Card>

        {/* Step 3 — Lessons */}
        <Card className="mb-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900">{t('zhuke.step3_title')}</h2>
            <span className="text-xs text-gray-500">{t('zhuke.lessons_count').replace('{n}', String(lessons.length))}</span>
          </div>

          {lessons.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 p-3 rounded-lg bg-gray-50 border border-gray-100">
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t('zhuke.default_week_start')}</label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={defaultWeekStart}
                  onChange={(e) =>
                    setDefaultWeekStart(Math.max(1, parseInt(e.target.value || '1', 10) || 1))
                  }
                  className="w-full px-2 py-1.5 rounded border border-gray-300 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t('zhuke.default_weekday')}</label>
                <input
                  value={defaultWeekday}
                  onChange={(e) => setDefaultWeekday(e.target.value)}
                  placeholder="一 / 二 / 日"
                  className="w-full px-2 py-1.5 rounded border border-gray-300 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">
                  {t('zhuke.default_periods')}<span className="text-red-500">*</span>
                </label>
                <input
                  value={defaultPeriods}
                  onChange={(e) => setDefaultPeriods(e.target.value)}
                  placeholder="3、4"
                  className="w-full px-2 py-1.5 rounded border border-gray-300 text-sm"
                />
              </div>
              <div className="flex items-end">
                <Button size="sm" variant="secondary" onClick={applyDefaultsToAll}>
                  {t('zhuke.apply_defaults')}
                </Button>
              </div>
            </div>
          )}

          {!lessons.length ? (
            <p className="text-sm text-gray-400 text-center py-6">{t('zhuke.lessons_empty')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_lesson_no')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_week')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_weekday')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_periods')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_date')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_hours')}</th>
                    <th className="px-2 py-2 text-left font-medium">{t('zhuke.col_content')}</th>
                    <th className="px-2 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {lessons.map((l, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-2 py-1.5 text-gray-500 tabular-nums">{l.lesson_no || idx + 1}</td>
                      <CellInput value={l.week || ''} onChange={(v) => updateLesson(idx, { week: v })} width={50} />
                      <CellInput value={l.weekday || ''} onChange={(v) => updateLesson(idx, { weekday: v })} width={60} />
                      <CellInput value={l.periods || ''} onChange={(v) => updateLesson(idx, { periods: v })} width={70} />
                      <CellInput value={l.date || ''} onChange={(v) => updateLesson(idx, { date: v })} width={110} />
                      <CellInput value={l.hours || ''} onChange={(v) => updateLesson(idx, { hours: v })} width={70} />
                      <CellInput value={l.content || ''} onChange={(v) => updateLesson(idx, { content: v })} grow />
                      <td className="px-2 py-1.5 text-right">
                        <button onClick={() => removeLesson(idx)} className="p-1 text-gray-400 hover:text-red-500" title={t('zhuke.remove_row')}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* My recent generations — visible whenever the user has any history. */}
        {history.length > 0 && (
          <Card className="mb-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-gray-900">
                {t('zhuke.history_title')}
              </h2>
              <Link
                to="/semester-helper/zhuke/history"
                className="text-xs text-brand-600 hover:text-brand-700 inline-flex items-center gap-0.5"
              >
                {t('zhuke.history_view_all')}
              </Link>
            </div>
            <ul className="divide-y divide-gray-100 text-xs">
              {history.map((h) => {
                const isGenerating = h.status === 'queued' || h.status === 'running'
                const fileRecovering =
                  !isGenerating &&
                  (h.recovering ||
                    (h.status === 'done' && h.file_exists === false) ||
                    h.recover_action === 'relayout_queued')
                const fileMissing =
                  !fileRecovering &&
                  !isGenerating &&
                  ((h.status === 'failed' && h.file_exists === false) ||
                    h.recover_action === 'impossible')
                const statusLabel = isGenerating
                  ? h.status === 'running'
                    ? t('zhuke.status_running')
                    : t('zhuke.status_queued')
                  : fileRecovering
                  ? h.recover_action === 'relayout_queued'
                    ? t('zhuke.layout_fixing')
                    : t('zhuke.recovering_file')
                  : fileMissing
                  ? t('doc.file_missing_badge')
                  : h.status === 'done'
                  ? t('zhuke.status_done')
                  : h.status === 'failed'
                  ? t('zhuke.status_failed')
                  : h.status
                const statusColor = isGenerating || fileRecovering
                  ? 'text-amber-600'
                  : fileMissing
                  ? 'text-red-600'
                  : h.status === 'done'
                  ? 'text-green-600'
                  : h.status === 'failed'
                  ? 'text-red-600'
                  : 'text-amber-600'
                const canDownload =
                  h.status === 'done' &&
                  !!h.result_id &&
                  h.file_exists !== false &&
                  !fileRecovering
                return (
                  <li
                    key={h.record_id}
                    className="py-2 flex items-center justify-between gap-3 flex-wrap"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-800 truncate">
                        {h.course_name || '未命名'}
                        <span className="text-gray-400 ml-2 font-normal">
                          {new Date(h.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-gray-500 flex gap-3 mt-0.5">
                        <span>{h.lessons_count} 节</span>
                        <span className={statusColor}>{statusLabel}</span>
                        {h.failures_count > 0 && (
                          <span className="text-amber-600">
                            {t('zhuke.progress_failures').replace(
                              '{f}',
                              String(h.failures_count),
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                    {canDownload && (
                      <div className="flex gap-1.5 shrink-0">
                        <button
                          onClick={() => doDownloadById(h.result_id, 'docx', h.file_name)}
                          disabled={!!downloading}
                          className="px-2 py-1 rounded border border-gray-200 hover:bg-gray-50 inline-flex items-center gap-1"
                        >
                          <Download className="w-3 h-3" />
                          docx
                        </button>
                        <button
                          onClick={() => doDownloadById(h.result_id, 'pdf', h.file_name)}
                          disabled={!!downloading}
                          className="px-2 py-1 rounded border border-gray-200 hover:bg-gray-50 inline-flex items-center gap-1"
                        >
                          <FileText className="w-3 h-3" />
                          pdf
                        </button>
                      </div>
                    )}
                    {fileRecovering && (
                      <span className="text-amber-600 shrink-0 inline-flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {h.recover_action === 'relayout_queued'
                          ? t('zhuke.layout_fixing')
                          : t('zhuke.recovering_file')}
                      </span>
                    )}
                    {isGenerating && (
                      <span className="text-amber-600 shrink-0 inline-flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {h.status === 'running'
                          ? t('zhuke.status_running')
                          : t('zhuke.status_queued')}
                      </span>
                    )}
                    {fileMissing && h.recover_action === 'impossible' && (
                      <Link
                        to="/semester-helper/zhuke"
                        className="inline-flex items-center gap-1 px-2 py-1 rounded border border-brand-200 text-xs text-brand-700 hover:bg-brand-50 shrink-0"
                      >
                        <Sparkles className="w-3 h-3" />
                        {t('doc.regenerate')}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </Card>
        )}

        {/* Step 4 — Generate & Download */}
        <Card>
          <h2 className="text-base font-semibold text-gray-900 mb-3">{t('zhuke.step4_title')}</h2>
          <p className="text-xs text-gray-500 mb-3">
            {t('zhuke.step4_hint')}
          </p>
          {backendReady === false && (
            <p className="text-xs text-red-600 mb-3">{t('zhuke.backend_unreachable')}</p>
          )}
          <label className="inline-flex items-center gap-2 text-xs text-gray-600 mb-3">
            <input type="checkbox" checked={skipAi} onChange={(e) => setSkipAi(e.target.checked)} />
            {t('zhuke.skip_ai')}
          </label>
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              onClick={doGenerate}
              disabled={!canGenerate || generating || phase === 'queued' || phase === 'running'}
            >
              {generating || phase === 'queued' || phase === 'running' ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1.5" />
              )}
              {phase === 'queued' || phase === 'running'
                ? t('zhuke.generating')
                : t('zhuke.generate')}
            </Button>
            {(phase === 'queued' || phase === 'running' || (!!recoverRid && autoRecovering)) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => void doStop()}
                disabled={stopping}
                className="text-amber-700 hover:text-amber-800 hover:bg-amber-50"
              >
                {stopping ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                ) : (
                  <Square className="w-4 h-4 mr-1.5" />
                )}
                {t('zhuke.stop_generate')}
              </Button>
            )}
            {(phase === 'failed' || phase === 'cancelled' || (phase === 'done' && generated && !fileReady)) &&
              (!recoverRid || !autoRecovering) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => void doRegenerate()}
                disabled={regenerating}
                className="text-brand-700 hover:text-brand-800 hover:bg-brand-50"
              >
                {regenerating ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                ) : (
                  <Play className="w-4 h-4 mr-1.5" />
                )}
                {t('zhuke.regenerate')}
              </Button>
            )}
            {progress.failures > 0 &&
              phase !== 'running' &&
              phase !== 'queued' &&
              (generated?.result_id || recoverRid) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => void doRetryFailed()}
                disabled={regenerating}
                className="text-amber-700 hover:text-amber-800 hover:bg-amber-50"
              >
                {regenerating ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 mr-1.5" />
                )}
                {t('zhuke.retry_failed').replace('{n}', String(progress.failures))}
              </Button>
            )}
            {generated && phase === 'done' && fileReady && (
              <>
                <span className="text-xs text-green-600 inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {t('zhuke.generate_done').replace('{n}', String(generated.lessons_count))}
                </span>
                <Button size="sm" variant="secondary" onClick={() => doDownload('docx')} disabled={!!downloading}>
                  {downloading === 'docx' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Download className="w-3.5 h-3.5 mr-1" />}
                  {t('zhuke.download_docx')}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => doDownload('pdf')} disabled={!!downloading}>
                  {downloading === 'pdf' ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <FileText className="w-3.5 h-3.5 mr-1" />}
                  {t('zhuke.download_pdf')}
                </Button>
              </>
            )}
            {generated && phase === 'done' && !fileReady && autoRecovering && (
              <span className="text-xs text-amber-600 inline-flex items-center gap-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {t('zhuke.file_recovering')}
              </span>
            )}
            {generated && phase === 'done' && !fileReady && !autoRecovering && (
              <span className="text-xs text-amber-600 inline-flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                {t('zhuke.file_missing_hint')}
              </span>
            )}
          </div>

          {(phase === 'queued' || phase === 'running') && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                <span>
                  {phase === 'queued'
                    ? t('zhuke.queued')
                    : progressLabel(progress, lessons.length, t)}
                </span>
                {progress.failures > 0 && phase !== 'queued' && (
                  <span className="text-amber-600">
                    {t('zhuke.progress_success_failures').replace('{f}', String(progress.failures))}
                  </span>
                )}
              </div>
              <div className="w-full h-2 bg-gray-100 rounded overflow-hidden">
                <div
                  className="h-full bg-brand-500 transition-all"
                  style={{
                    width: `${
                      progress.total > 0
                        ? Math.min(100, (progress.done / progress.total) * 100)
                        : 0
                    }%`,
                  }}
                />
              </div>
              {phase === 'running' && (
                <p className="text-xs text-gray-500 mt-1">{t('zhuke.progress_running_sub')}</p>
              )}
              {stalledReason === 'queued_timeout' && (
                <p className="text-xs text-red-600 mt-2 inline-flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {t('zhuke.stalled_queued')}
                </p>
              )}
              {stalledReason === 'no_progress' && (
                <p className="text-xs text-red-600 mt-2 inline-flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {t('zhuke.stalled_running')}
                </p>
              )}
              {/* Heartbeat line — shows what worker is currently doing during
                  the 60-180s Kimi wait, plus a rough ETA based on average
                  lesson duration so far. Both pieces only render when we
                  actually have signal (avoids "正在生成第 0 节" or "approx 0m
                  0s" placeholders before the first lesson finishes). */}
              {currentLessonIdx !== null && phase === 'running' && (
                <div className="text-xs text-brand-700 inline-flex items-center gap-2 mt-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>
                    {t('zhuke.now_generating')
                      .replace('{n}', String(currentLessonIdx + 1))
                      .replace('{title}', currentLessonTitle || '...')}
                  </span>
                  {startedAt && progress.total > 0 && (() => {
                    const eta = etaLabel(
                      startedAt,
                      progress.done,
                      progress.total,
                      progress.failures,
                      t,
                    )
                    return eta ? (
                      <span className="text-gray-400">· {eta}</span>
                    ) : null
                  })()}
                </div>
              )}
              <p className="text-xs text-amber-600 mt-2 inline-flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                {t('zhuke.generate_long_hint').replace('{n}', String(lessons.length))}
              </p>
            </div>
          )}

          {/* Per-lesson live preview cards. Visible whenever we have at
              least one preview lesson (running OR done): users keep seeing
              the cards after completion for quick scan before download. */}
          {Object.keys(previewLessons).length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-medium text-gray-700 mb-2">
                {t('zhuke.preview_section_title').replace(
                  '{done}',
                  String(Object.keys(previewLessons).length),
                )}
              </div>
              <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 bg-white">
                {Object.values(previewLessons)
                  .sort((a, b) => a.lesson_idx - b.lesson_idx)
                  .map((l) => (
                    <PreviewLessonCard key={l.lesson_idx} lesson={l} t={t} />
                  ))}
              </div>
            </div>
          )}

          {phase === 'failed' && failureNote && (
            <p className="text-xs text-red-600 mt-3 inline-flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {failureNote}
            </p>
          )}
          {phase === 'cancelled' && (
            <p className="text-xs text-gray-600 mt-3 inline-flex items-center gap-1">
              <Square className="w-3 h-3" />
              {failureNote || t('zhuke.cancelled_by_user')}
            </p>
          )}
        </Card>
      </main>
    </div>
  )
}

function Field({ label, value, onChange, required }: { label: string; value: string; onChange: (v: string) => void; required?: boolean }) {
  return (
    <div>
      <label className="block text-xs text-gray-600 mb-1">
        {label}{required && <span className="text-red-500">*</span>}
      </label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2 py-1.5 rounded border border-gray-300 text-sm"
      />
    </div>
  )
}

function CellInput({ value, onChange, width, grow }: { value: string; onChange: (v: string) => void; width?: number; grow?: boolean }) {
  return (
    <td className="px-1 py-1">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={width ? { width } : undefined}
        className={`px-1.5 py-1 rounded border border-gray-200 text-xs ${grow ? 'w-full min-w-[220px]' : ''}`}
      />
    </td>
  )
}

/**
 * Progress line: success count when running, plain done/total when queued context.
 */
function progressLabel(
  progress: { done: number; total: number; failures: number },
  fallbackTotal: number,
  t: (k: string) => string,
): string {
  const total = progress.total || fallbackTotal
  const success = Math.max(0, progress.done - progress.failures)
  return t('zhuke.progress_success')
    .replace('{success}', String(success))
    .replace('{total}', String(total))
}

/**
 * Compute remaining time from start + successful-lesson rate. Failed lessons are
 * excluded from the average so timeout retries do not inflate ETA to ~86 min.
 * Returns empty string when ETA should be hidden.
 */
function etaLabel(
  startedAt: number,
  done: number,
  total: number,
  failures: number,
  t: (k: string) => string,
): string {
  if (total <= 0 || done >= total) return ''
  const successDone = Math.max(0, done - failures)
  if (done > 0 && failures / done > 0.5) {
    return t('zhuke.eta_high_failures')
  }
  if (successDone < 1) {
    return t('zhuke.eta_waiting_first')
  }
  const elapsedMs = Math.max(0, Date.now() - startedAt)
  const perLessonMs = elapsedMs / successDone
  const remaining = total - done
  const remainingMs = Math.min(perLessonMs * remaining, 30 * 60 * 1000)
  const totalSec = Math.round(Math.max(0, remainingMs) / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return t('zhuke.eta_remaining').replace('{m}', String(m)).replace('{s}', String(s))
}

/**
 * Collapsible per-lesson preview card. Renders the lesson title + meta in the
 * summary row; expanded body lists each of the 9 sections with title + body
 * (line-clamp-3, click section to expand). Failed lessons get a red badge.
 */
function PreviewLessonCard({
  lesson, t,
}: {
  lesson: PreviewLesson
  t: (k: string) => string
}) {
  const sectionCount = Object.keys(lesson.sections || {}).length
  return (
    <details className="group" open={false}>
      <summary className="px-3 py-2 text-xs cursor-pointer hover:bg-gray-50 flex items-center justify-between gap-2 list-none">
        <span className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-gray-400 shrink-0">
            {t('zhuke.preview_lesson_label').replace('{n}', String(lesson.lesson_idx + 1))}
          </span>
          <span className="font-medium text-gray-800 truncate">
            {lesson.title || '...'}
          </span>
          {lesson.time_label && (
            <span className="text-gray-400 truncate hidden sm:inline">
              · {lesson.time_label}
            </span>
          )}
          {lesson.hours && (
            <span className="text-gray-400 hidden sm:inline">· {lesson.hours}</span>
          )}
        </span>
        <span className="flex items-center gap-2 shrink-0">
          {lesson.failed ? (
            <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-50 text-red-600">
              <AlertTriangle className="w-3 h-3" />
              {t('zhuke.preview_failed_badge')}
            </span>
          ) : (
            <span className="text-[10px] text-gray-400">
              {sectionCount > 0 ? `${sectionCount} sections` : t('zhuke.preview_expand_hint')}
            </span>
          )}
          <span className="text-gray-300 group-open:rotate-90 transition-transform">›</span>
        </span>
      </summary>
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 space-y-2">
        {sectionCount === 0 ? (
          <p className="text-xs text-gray-400">
            {lesson.failed
              ? t('zhuke.preview_failed_badge')
              : t('zhuke.preview_expand_hint')}
          </p>
        ) : (
          Object.entries(lesson.sections).map(([sectionKey, sectionBody]) => (
            <details key={sectionKey} className="group/sec">
              <summary className="text-xs cursor-pointer text-gray-700 hover:text-brand-700 list-none flex items-start gap-1">
                <span className="text-gray-300 group-open/sec:rotate-90 transition-transform mt-0.5">›</span>
                <span className="font-medium">{sectionKey}</span>
              </summary>
              <pre className="mt-1 ml-4 text-[11px] text-gray-600 whitespace-pre-wrap font-sans leading-relaxed">
                {sectionBody || '(空)'}
              </pre>
            </details>
          ))
        )}
      </div>
    </details>
  )
}
