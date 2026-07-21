import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ZHUKE_API_TIMEOUT_MS, ZHUKE_LIST_TIMEOUT_MS } from '../services/api'

import { toast } from '../components/ui/Toast'



export type ZhukeRecoverResponse = {

  action: string

  file_exists: boolean

  status: string

  enqueued: number

  layout_enqueued: number

  message: string

  recovering: boolean

}



export type ZhukeCancelResponse = {

  cancelled: number

  file_exists: boolean

  status: string

  message: string

}



export type ZhukeStatusResponse = {

  result_id: string

  status: string

  done: number

  total: number

  failures: number

  success_done?: number

  file_name?: string

  error?: string

  file_exists?: boolean

  recovering?: boolean

  recover_action?: string | null

  stalled_reason?: 'queued_timeout' | 'no_progress' | null

  lessons?: Array<{

    lesson_idx: number

    title?: string

    time_label?: string

    hours?: string

    sections?: Record<string, string>

    failed?: boolean

  }>

}



export type ZhukeReloadOptions = { silent?: boolean }



const sessionTriggered = new Set<string>()

let recoverApiAvailable: boolean | null = null



function isRecoverNotFound(err: unknown): boolean {

  const status = (err as { response?: { status?: number } })?.response?.status

  return status === 404

}



export async function postZhukeCancel(resultId: string): Promise<ZhukeCancelResponse> {

  const res = await api.post<ZhukeCancelResponse>(

    `/api/v1/semester-helper/zhuke/${encodeURIComponent(resultId)}/cancel`,

    {},

    { timeout: ZHUKE_API_TIMEOUT_MS },

  )

  return res.data

}



/** Allow recover to be triggered again after user stops a batch. */

export function clearZhukeRecoverSession(resultId: string) {

  sessionTriggered.delete(resultId)

}



/** Mark recover as already POSTed (e.g. after postZhukeRegenerate). */

export function markZhukeRecoverSessionTriggered(resultId: string) {

  sessionTriggered.add(resultId)

}



export function isZhuke409(err: unknown): boolean {

  return (err as { response?: { status?: number } })?.response?.status === 409

}



/** Shared 409 handler for generate / regenerate / stop / download. */

export async function handleZhuke409(

  err: unknown,

  t: (key: string) => string,

  fallbackKey = 'zhuke.active_batch_conflict',

): Promise<string> {

  if (isZhuke409(err)) {

    return t(fallbackKey)

  }

  const { readApiErrorDetail } = await import('../lib/blobError')

  return readApiErrorDetail(err, t(fallbackKey))

}



export async function postZhukeRecover(

  resultId: string,

  options?: { forceLayout?: boolean; mode?: 'rebuild' | 'full' },

): Promise<ZhukeRecoverResponse> {

  const res = await api.post<ZhukeRecoverResponse>(

    `/api/v1/semester-helper/zhuke/${encodeURIComponent(resultId)}/recover`,

    {

      force_layout: options?.forceLayout ?? false,

      mode: options?.mode ?? 'rebuild',

    },

    { timeout: ZHUKE_API_TIMEOUT_MS },

  )

  return res.data

}



/** Full regeneration: requeue missing lessons and relayout when needed. */

export async function postZhukeRegenerate(

  resultId: string,

  options?: { forceLayout?: boolean },

): Promise<ZhukeRecoverResponse> {

  clearZhukeRecoverSession(resultId)

  const res = await postZhukeRecover(resultId, { ...options, mode: 'full' })

  markZhukeRecoverSessionTriggered(resultId)

  return res

}



/** POST /recover with 404 detection — falls back when backend is stale. */

export async function tryPostZhukeRecover(

  resultId: string,

  options?: { forceLayout?: boolean; mode?: 'rebuild' | 'full' },

): Promise<{ ok: boolean; unavailable: boolean; data?: ZhukeRecoverResponse }> {

  if (recoverApiAvailable === false) {

    return { ok: false, unavailable: true }

  }

  if (sessionTriggered.has(resultId)) {

    return { ok: false, unavailable: false }

  }

  sessionTriggered.add(resultId)

  try {

    const data = await postZhukeRecover(resultId, options)

    recoverApiAvailable = true

    return { ok: true, unavailable: false, data }

  } catch (err) {

    if (isRecoverNotFound(err)) {

      recoverApiAvailable = false

      return { ok: false, unavailable: true }

    }

    sessionTriggered.delete(resultId)

    throw err

  }

}



export async function fetchZhukeStatus(
  resultId: string,
  options?: { light?: boolean },
): Promise<ZhukeStatusResponse> {
  const light = options?.light ?? false
  const res = await api.get<ZhukeStatusResponse>(
    `/api/v1/semester-helper/zhuke/${encodeURIComponent(resultId)}/status`,
    {
      params: light ? { light: 1 } : undefined,
      timeout: light ? ZHUKE_LIST_TIMEOUT_MS : ZHUKE_API_TIMEOUT_MS,
    },
  )
  return res.data
}



/** Whether a row is recovering a missing/broken file (not first-time generation). */

export function zhukeIsActiveRecover(item: {

  recovering?: boolean

  status?: string

  file_exists?: boolean

  recover_action?: string | null

}): boolean {

  if (!item.recovering) return false

  if (item.recover_action === 'relayout_queued') return true

  if (item.status === 'done' && item.file_exists === false) return true

  if (item.recover_action && item.recover_action !== 'noop') return true

  // Backend sets recovering=true for any active queue job — exclude in-flight generation.

  if (item.status === 'queued' || item.status === 'running') return false

  return false

}



/** Whether a batch still has queued/running queue work (generation or recovery). */

export function zhukeHasActiveJobs(item: {

  recovering?: boolean

  status?: string

}): boolean {

  return item.status === 'queued' || item.status === 'running' || !!item.recovering

}



/** Poll history list while any row has active queue work. */

export function useZhukeHistoryPoll(

  items: Array<{ recovering?: boolean; status?: string }>,

  reload: (opts?: ZhukeReloadOptions) => void | Promise<void>,

) {

  const reloadRef = useRef(reload)

  reloadRef.current = reload



  useEffect(() => {

    const needsPoll = items.some((h) => zhukeHasActiveJobs(h))

    if (!needsPoll) return

    const id = window.setInterval(() => void reloadRef.current({ silent: true }), 8000)

    return () => window.clearInterval(id)

  }, [items])

}



/**

 * Auto-trigger POST /recover once per result_id per session, then poll /status.

 * Used only for in-flight generation resume (localStorage active rid), not history lists.

 */

export function useZhukeAutoRecover(options: {

  resultId: string | null | undefined

  enabled: boolean

  t: (key: string) => string

  onStatus?: (status: ZhukeStatusResponse) => void

  onComplete?: () => void

  onImpossible?: () => void

  onStalled?: () => void

  /** When false, only poll /status (no POST /recover). Default false — auto-recover

   *  was triggering unwanted regeneration after user-cancel. Pass true only

   *  from explicit user-driven regenerate flows. */

  autoPostRecover?: boolean

}) {

  const {

    resultId,

    enabled,

    t,

    onStatus,

    onComplete,

    onImpossible,

    onStalled,

    autoPostRecover = false,

  } = options

  const [recovering, setRecovering] = useState(false)

  const [impossible, setImpossible] = useState(false)

  const pollRef = useRef<number | null>(null)



  const stopPoll = useCallback(() => {

    if (pollRef.current != null) {

      window.clearInterval(pollRef.current)

      pollRef.current = null

    }

  }, [])



  useEffect(() => {

    if (!enabled || !resultId) {

      setRecovering(false)

      return

    }



    let cancelled = false

    let idlePolls = 0

    setRecovering(true)



    const pollOnce = async (): Promise<'done' | 'impossible' | 'stalled' | 'continue'> => {

      try {

        const s = await fetchZhukeStatus(resultId, { light: true })

        if (cancelled) return 'continue'

        onStatus?.(s)

        if (s.recover_action === 'impossible') {

          return 'impossible'

        }

        if (s.status === 'failed' && !s.recovering) {

          return 'stalled'

        }

        if (s.file_exists !== false && s.status === 'done') {

          return 'done'

        }

        if (s.status === 'done' && s.file_exists === false && !s.recovering) {

          return 'stalled'

        }

        if (!s.recovering && s.status !== 'queued' && s.status !== 'running') {

          idlePolls += 1

          if (idlePolls >= 6) return 'stalled'

        } else {

          idlePolls = 0

        }

        if (!s.recovering && s.file_exists !== false) {

          return 'done'

        }

      } catch {

        /* next tick */

      }

      return 'continue'

    }



    const finishStalled = () => {

      stopPoll()

      setRecovering(false)

    }



    const startPolling = async () => {

      const first = await pollOnce()

      if (cancelled) return

      if (first === 'done') {

        setRecovering(false)

        onComplete?.()

        return

      }

      if (first === 'impossible') {

        setImpossible(true)

        setRecovering(false)

        onImpossible?.()

        toast.error(t('zhuke.recover_impossible'))

        return

      }

      if (first === 'stalled') {

        finishStalled()

        onStalled?.()

        return

      }



      pollRef.current = window.setInterval(async () => {

        const outcome = await pollOnce()

        if (outcome === 'done') {

          stopPoll()

          setRecovering(false)

          onComplete?.()

        } else if (outcome === 'impossible') {

          stopPoll()

          setImpossible(true)

          setRecovering(false)

          onImpossible?.()

          toast.error(t('zhuke.recover_impossible'))

        } else if (outcome === 'stalled') {

          finishStalled()

          onStalled?.()

        }

      }, 8000)

    }



    ;(async () => {

      try {

        if (autoPostRecover) {

          const attempt = await tryPostZhukeRecover(resultId, { mode: 'rebuild' })

          if (cancelled) return



          if (attempt.ok && attempt.data) {

            const r = attempt.data

            if (r.action === 'impossible') {

              setImpossible(true)

              setRecovering(false)

              onImpossible?.()

              toast.error(t('zhuke.recover_impossible'))

              return

            }

            if (r.file_exists && !r.recovering) {

              setRecovering(false)

              onComplete?.()

              return

            }

          }

        }



        await startPolling()

      } catch {

        if (!cancelled) {

          setRecovering(false)

        }

      }

    })()



    return () => {

      cancelled = true

      stopPoll()

    }

  }, [autoPostRecover, enabled, onComplete, onImpossible, onStalled, onStatus, resultId, stopPoll, t])



  return { recovering, impossible }

}


