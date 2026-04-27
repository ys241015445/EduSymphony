import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/layout/Header'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Input from '../components/ui/Input'
import { useT } from '../i18n/translations'
import { api } from '../services/api'
import {
  Upload, FileEdit, Sparkles, Loader2, Download, ChevronLeft,
  CheckCircle2, AlertTriangle, FileText, X, RefreshCw, Wand2,
} from 'lucide-react'

// ────────────────────────────── types ──────────────────────────────

interface Placeholder {
  key: string
  raw: string
  pattern: string
  count: number
  sample_context: string
}

interface AnalyzeResponse {
  token: string
  original_name: string
  original_ext: string
  placeholders: Placeholder[]
  mode: 'token' | 'ai_detect'
  preview_text: string
}

interface GenerateResponse {
  id: string
  original_ext: string
  mode: 'token' | 'ai_detect'
  fill_map: Record<string, string> | null
  filled_text_preview: string | null
  supported_formats: string[]
}

interface HistoryItem {
  id: string
  intent: string
  mode: string
  original_ext: string
  created_at: string
}

const ACCEPT = '.docx,.pptx,.xlsx,.txt,.md'
const ALL_FORMATS = ['docx', 'pptx', 'xlsx', 'txt', 'md', 'pdf', 'json'] as const
type Format = typeof ALL_FORMATS[number]

// which output formats make sense for a given source ext
const FORMAT_MATRIX: Record<string, Format[]> = {
  docx: ['docx', 'pdf', 'txt', 'md', 'json'],
  pptx: ['pptx', 'pdf', 'txt', 'md', 'json'],
  xlsx: ['xlsx', 'txt', 'md', 'json'],
  txt: ['txt', 'md', 'docx', 'pdf', 'json'],
  md: ['md', 'txt', 'docx', 'pdf', 'json'],
}

// ────────────────────────────── component ──────────────────────────────

export default function TemplateFill() {
  const t = useT()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // step 1: file
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)

  // step 2: intent
  const [intent, setIntent] = useState('')
  const [provider, setProvider] = useState('qwen')

  // step 3: analyze
  const [analyzed, setAnalyzed] = useState<AnalyzeResponse | null>(null)

  // step 4: generate
  const [generated, setGenerated] = useState<GenerateResponse | null>(null)
  const [editableMap, setEditableMap] = useState<Record<string, string>>({})

  // history
  const [history, setHistory] = useState<HistoryItem[]>([])

  // ui state
  const [loading, setLoading] = useState(false)
  const [loadingAction, setLoadingAction] = useState<'analyze' | 'generate' | ''>('')
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const res = await api.get('/api/v1/template-fill/history')
      setHistory(res.data || [])
    } catch {
      // ignore
    }
  }

  // ── file handling ───────────────────────────────────────

  const onPickFile = (f: File | null) => {
    if (!f) return
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    if (!['docx', 'pptx', 'xlsx', 'txt', 'md'].includes(ext)) {
      setError(t('template.err_unsupported_ext'))
      return
    }
    if (f.size > 20 * 1024 * 1024) {
      setError(t('template.err_too_large'))
      return
    }
    setFile(f)
    setAnalyzed(null)
    setGenerated(null)
    setEditableMap({})
    setError('')
    setSuccessMsg('')
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) onPickFile(f)
  }

  // ── analyze ─────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!file) {
      setError(t('template.err_no_file'))
      return
    }
    setLoading(true)
    setLoadingAction('analyze')
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post<AnalyzeResponse>('/api/v1/template-fill/analyze', fd)
      setAnalyzed(res.data)
      setGenerated(null)
      // 预填充 editable map
      const m: Record<string, string> = {}
      res.data.placeholders.forEach((p) => { m[p.key] = '' })
      setEditableMap(m)
      setSuccessMsg(
        res.data.mode === 'token'
          ? t('template.msg_token_mode')
          : t('template.msg_ai_detect_mode'),
      )
    } catch (e: any) {
      setError(e?.response?.data?.detail || t('template.err_analyze_failed'))
    } finally {
      setLoading(false)
      setLoadingAction('')
    }
  }

  // ── generate ────────────────────────────────────────────

  const handleGenerate = async (useEditedMap = false) => {
    if (!analyzed) return
    if (!intent.trim() && !useEditedMap) {
      setError(t('template.err_no_intent'))
      return
    }
    setLoading(true)
    setLoadingAction('generate')
    setError('')
    try {
      const fd = new FormData()
      fd.append('token', analyzed.token)
      fd.append('intent', intent)
      fd.append('provider', provider)
      fd.append('mode', analyzed.mode)
      if (useEditedMap) {
        fd.append('fill_map', JSON.stringify(editableMap))
      }
      const res = await api.post<GenerateResponse>('/api/v1/template-fill/generate', fd)
      setGenerated(res.data)
      if (res.data.fill_map) {
        setEditableMap(res.data.fill_map)
      }
      setSuccessMsg(t('template.msg_generated'))
      loadHistory()
    } catch (e: any) {
      setError(e?.response?.data?.detail || t('template.err_generate_failed'))
    } finally {
      setLoading(false)
      setLoadingAction('')
    }
  }

  // ── download ────────────────────────────────────────────

  const handleDownload = async (id: string, format: Format, srcExt?: string) => {
    setError('')
    try {
      const res = await api.get(`/api/v1/template-fill/${id}/download`, {
        params: { format },
        responseType: 'blob',
      })
      const disp = String(res.headers['content-disposition'] || '')
      let filename = `template_fill.${format}`
      const m = disp.match(/filename\*=UTF-8''([^;]+)/) || disp.match(/filename="([^"]+)"/)
      if (m) filename = decodeURIComponent(m[1])
      const lossy = res.headers['x-conversion-lossy'] === '1'

      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)

      if (lossy && srcExt && format !== srcExt) {
        setSuccessMsg(t('template.warn_lossy'))
      } else {
        setSuccessMsg(t('template.msg_downloaded'))
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || t('template.err_download_failed'))
    }
  }

  // ── render ──────────────────────────────────────────────

  const formats: Format[] = analyzed
    ? (FORMAT_MATRIX[analyzed.original_ext] || ALL_FORMATS) as Format[]
    : [...ALL_FORMATS]

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-6">
          <Link to="/dashboard" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
            <ChevronLeft className="w-4 h-4" />
            {t('template.back')}
          </Link>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <FileEdit className="w-4 h-4 text-emerald-600" />
            {t('template.subtitle')}
          </div>
        </div>

        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Wand2 className="w-6 h-6 text-emerald-600" />
            {t('template.title')}
          </h1>
          <p className="text-sm text-gray-500 mt-1">{t('template.desc')}</p>
        </div>

        {/* Banners */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div className="flex-1">{error}</div>
            <button onClick={() => setError('')} className="text-red-500 hover:text-red-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        {successMsg && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <div className="flex-1">{successMsg}</div>
            <button onClick={() => setSuccessMsg('')} className="text-emerald-600 hover:text-emerald-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Step 1: Upload */}
        <Card className="mb-5">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">1</span>
            {t('template.step_upload')}
          </h2>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all
              ${dragOver ? 'border-emerald-500 bg-emerald-50' : 'border-gray-300 bg-gray-50 hover:border-emerald-400'}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => onPickFile(e.target.files?.[0] || null)}
            />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileText className="w-6 h-6 text-emerald-600" />
                <div className="text-left">
                  <div className="font-medium text-gray-900">{file.name}</div>
                  <div className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); setAnalyzed(null); setGenerated(null) }}
                  className="ml-3 p-1 text-gray-400 hover:text-red-500"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <>
                <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                <div className="text-sm text-gray-700 font-medium">{t('template.drop_hint')}</div>
                <div className="text-xs text-gray-400 mt-1">{t('template.support_formats')}</div>
              </>
            )}
          </div>
        </Card>

        {/* Step 2: Intent */}
        <Card className="mb-5">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">2</span>
            {t('template.step_intent')}
          </h2>
          <textarea
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder={t('template.intent_placeholder')}
            rows={4}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <div className="mt-3 flex items-center gap-3">
            <span className="text-xs text-gray-500">{t('template.provider')}：</span>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="rounded-md border border-gray-300 px-2 py-1 text-sm"
            >
              <option value="qwen">Qwen</option>
              <option value="doubao">Doubao</option>
              <option value="deepseek">Deepseek</option>
              <option value="kimi">Kimi</option>
            </select>
          </div>
        </Card>

        {/* Step 3: Analyze */}
        <Card className="mb-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">3</span>
              {t('template.step_analyze')}
            </h2>
            <Button
              onClick={handleAnalyze}
              disabled={!file || loading}
              variant="secondary"
              className="!border-emerald-300 !text-emerald-700 !bg-emerald-50 hover:!bg-emerald-100"
            >
              {loading && loadingAction === 'analyze' ? (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1.5" />
              )}
              {t('template.btn_analyze')}
            </Button>
          </div>
          {analyzed && (
            <div>
              <div className="mb-3 flex items-center gap-2 flex-wrap">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                  {analyzed.mode === 'token' ? t('template.badge_token') : t('template.badge_ai_detect')}
                </span>
                <span className="text-xs text-gray-500">
                  {t('template.placeholders_found')} {analyzed.placeholders.length}
                </span>
              </div>
              {analyzed.placeholders.length > 0 && (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-xs text-gray-500">
                      <tr>
                        <th className="text-left px-3 py-2">{t('template.col_key')}</th>
                        <th className="text-left px-3 py-2">{t('template.col_pattern')}</th>
                        <th className="text-left px-3 py-2">{t('template.col_count')}</th>
                        <th className="text-left px-3 py-2">{t('template.col_context')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analyzed.placeholders.map((p, idx) => (
                        <tr key={idx} className="border-t border-gray-100">
                          <td className="px-3 py-2 font-mono text-xs text-gray-800">{p.key}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">{p.pattern}</td>
                          <td className="px-3 py-2 text-xs text-gray-500">×{p.count}</td>
                          <td className="px-3 py-2 text-xs text-gray-400 truncate max-w-[280px]">{p.sample_context}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Step 4: Generate */}
        <Card className="mb-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">4</span>
              {t('template.step_generate')}
            </h2>
            <Button
              onClick={() => handleGenerate(false)}
              disabled={!analyzed || loading}
            >
              {loading && loadingAction === 'generate' ? (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              ) : (
                <Wand2 className="w-4 h-4 mr-1.5" />
              )}
              {t('template.btn_generate')}
            </Button>
          </div>

          {generated && generated.fill_map && (
            <div className="space-y-2 mb-3">
              <div className="text-xs text-gray-500 mb-1">{t('template.edit_map_hint')}</div>
              <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-96 overflow-auto">
                {Object.keys(editableMap).map((k) => (
                  <div key={k} className="flex items-start gap-3 px-3 py-2">
                    <div className="w-1/3 font-mono text-xs text-gray-700 pt-1.5 break-all">{k}</div>
                    <div className="flex-1">
                      <Input
                        value={editableMap[k] || ''}
                        onChange={(e) => setEditableMap({ ...editableMap, [k]: e.target.value })}
                        placeholder={t('template.value_placeholder')}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() => handleGenerate(true)}
                  disabled={loading}
                >
                  <RefreshCw className="w-4 h-4 mr-1.5" />
                  {t('template.btn_regen_with_edit')}
                </Button>
                <span className="text-xs text-gray-400">{t('template.regen_hint')}</span>
              </div>
            </div>
          )}

          {generated && generated.filled_text_preview && (
            <div className="mt-3">
              <div className="text-xs text-gray-500 mb-1">{t('template.preview')}</div>
              <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 whitespace-pre-wrap max-h-80 overflow-auto text-gray-700">
{generated.filled_text_preview}
              </pre>
            </div>
          )}
        </Card>

        {/* Step 5: Download */}
        {generated && (
          <Card className="mb-5">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">5</span>
              {t('template.step_download')}
            </h2>
            <div className="flex flex-wrap gap-2">
              {ALL_FORMATS.map((fmt) => {
                const compatible = formats.includes(fmt)
                const isPrimary = generated.original_ext === fmt
                return (
                  <Button
                    key={fmt}
                    variant="secondary"
                    disabled={!compatible}
                    onClick={() => handleDownload(generated.id, fmt, generated.original_ext)}
                    className={isPrimary ? '!border-emerald-300 !text-emerald-700 !bg-emerald-50 hover:!bg-emerald-100' : ''}
                  >
                    <Download className="w-4 h-4 mr-1.5" />
                    .{fmt}
                    {isPrimary && <span className="ml-1 text-[10px]">({t('template.primary')})</span>}
                  </Button>
                )
              })}
            </div>
            <div className="text-xs text-gray-400 mt-2">{t('template.format_hint')}</div>
          </Card>
        )}

        {/* History */}
        {history.length > 0 && (
          <Card>
            <h2 className="text-lg font-semibold mb-3">{t('template.history')}</h2>
            <div className="divide-y divide-gray-100">
              {history.map((h) => (
                <div key={h.id} className="py-2 flex items-center justify-between text-sm">
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-800 truncate">{h.intent || t('template.no_intent')}</div>
                    <div className="text-xs text-gray-400">
                      .{h.original_ext} · {h.mode} · {new Date(h.created_at).toLocaleString()}
                    </div>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() => handleDownload(h.id, h.original_ext as Format, h.original_ext)}
                  >
                    <Download className="w-4 h-4 mr-1.5" />
                    {t('template.btn_download_primary')}
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        )}
      </main>
    </div>
  )
}
