/** Default message when Vite proxy cannot reach uvicorn on :3002. */
export const BACKEND_UNREACHABLE_MSG =
  '后端服务未响应，请确认 3002 端口已启动（uvicorn）'

function isGenericServerError(detail: string | undefined, status?: number): boolean {
  const normalized = (detail || '').trim()
  if (!normalized || normalized === 'Internal Server Error' || normalized === 'Request failed') {
    return status === 500 || status === 502
  }
  return false
}

/** Parse FastAPI error JSON from an axios blob download failure. */
export async function readApiErrorDetail(
  err: unknown,
  fallback = 'Request failed',
  backendUnreachable = BACKEND_UNREACHABLE_MSG,
): Promise<string> {
  const ax = err as {
    response?: { data?: unknown; status?: number; statusText?: string }
    message?: string
    code?: string
  }

  if (!ax?.response) {
    const msg = ax?.message || ''
    if (ax?.code === 'ERR_NETWORK' || /network error/i.test(msg)) {
      return backendUnreachable
    }
  }

  const status = ax?.response?.status
  const data = ax?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      if (!text) {
        return isGenericServerError(undefined, status) ? backendUnreachable : fallback
      }
      try {
        const parsed = JSON.parse(text) as { detail?: unknown }
        if (typeof parsed.detail === 'string') {
          return isGenericServerError(parsed.detail, status)
            ? backendUnreachable
            : parsed.detail
        }
        if (parsed.detail != null) return String(parsed.detail)
      } catch {
        if (isGenericServerError(text, status)) return backendUnreachable
        return text.slice(0, 500)
      }
    } catch {
      /* fall through */
    }
  }
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return isGenericServerError(detail, status) ? backendUnreachable : detail
    }
    if (detail != null) return String(detail)
  }
  if (typeof data === 'string' && data) {
    return isGenericServerError(data, status) ? backendUnreachable : data
  }

  const statusText = ax?.response?.statusText
  if (isGenericServerError(statusText, status)) return backendUnreachable
  return statusText || ax?.message || fallback
}
