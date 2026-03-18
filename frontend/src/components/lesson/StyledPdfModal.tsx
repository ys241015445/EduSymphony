import { useState, useRef } from 'react'
import { X, Upload, FileText, Loader2, AlertCircle } from 'lucide-react'
import { useStyledPdfStore } from '../../stores/styledPdfStore'

interface StyledPdfModalProps {
  lessonId: string
  lessonTitle: string
  hasDraft: boolean
  hasOptimized: boolean
  isGenerating?: boolean
  onClose: () => void
}

export default function StyledPdfModal({
  lessonId,
  lessonTitle,
  hasDraft,
  hasOptimized,
  isGenerating = false,
  onClose,
}: StyledPdfModalProps) {
  const startGeneration = useStyledPdfStore((s) => s.startGeneration)

  const [templateType, setTemplateType] = useState<'default' | 'upload'>('default')
  const [templateFile, setTemplateFile] = useState<File | null>(null)
  const [contentVersion, setContentVersion] = useState<'draft' | 'optimized'>(hasDraft ? 'draft' : 'optimized')
  const [error, setError] = useState('')

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!['txt', 'md', 'json', 'pdf'].includes(ext)) {
      setError('不支持的文件格式，请上传 txt、md、json 或 pdf 文件')
      return
    }
    setError('')
    setTemplateFile(file)
  }

  const handleGenerate = () => {
    if (templateType === 'upload' && !templateFile) return
    setError('')
    startGeneration(lessonId, templateType, contentVersion, templateFile)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-[560px] max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-100 flex items-center justify-center">
              <FileText className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">当地风格格式 PDF</h2>
              <p className="text-xs text-gray-500">基于范本格式，由 AI 生成排版精美的教案</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Template selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">范本选择</label>
            <div className="flex gap-3">
              <button
                onClick={() => { setTemplateType('default'); setTemplateFile(null) }}
                disabled={isGenerating}
                className={`flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${
                  templateType === 'default'
                    ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
              >
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  templateType === 'default' ? 'border-indigo-500' : 'border-gray-300'
                }`}>
                  {templateType === 'default' && <div className="w-2 h-2 rounded-full bg-indigo-500" />}
                </div>
                <div className="text-left">
                  <div className="text-sm font-medium text-gray-900">默认范本</div>
                  <div className="text-xs text-gray-500">澳门教案格式（旋轉對稱圖形教案）</div>
                </div>
              </button>
              <button
                onClick={() => setTemplateType('upload')}
                disabled={isGenerating}
                className={`flex-1 flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${
                  templateType === 'upload'
                    ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                } ${isGenerating ? 'opacity-60 cursor-not-allowed' : ''}`}
              >
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  templateType === 'upload' ? 'border-indigo-500' : 'border-gray-300'
                }`}>
                  {templateType === 'upload' && <div className="w-2 h-2 rounded-full bg-indigo-500" />}
                </div>
                <div className="text-left">
                  <div className="text-sm font-medium text-gray-900">上传范本</div>
                  <div className="text-xs text-gray-500">自定义格式模板</div>
                </div>
              </button>
            </div>
          </div>

          {/* File upload area */}
          {templateType === 'upload' && (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.json,.pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              <div
                onClick={() => !isGenerating && fileInputRef.current?.click()}
                className={`border-2 border-dashed border-gray-300 rounded-xl p-5 text-center transition-all ${
                  isGenerating ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30'
                }`}
              >
                {templateFile ? (
                  <div className="flex items-center justify-center gap-2 text-sm text-indigo-700">
                    <FileText className="w-5 h-5" />
                    <span className="font-medium">{templateFile.name}</span>
                    <span className="text-gray-400">({(templateFile.size / 1024).toFixed(1)} KB)</span>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600">点击上传范本文件</p>
                    <p className="text-xs text-gray-400 mt-1">支持 TXT、MD、JSON、PDF 格式</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Version selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">教案版本</label>
            <div className="flex gap-3">
              <button
                onClick={() => setContentVersion('draft')}
                disabled={!hasDraft || isGenerating}
                className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                  contentVersion === 'draft'
                    ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                } ${!hasDraft || isGenerating ? 'opacity-40 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    contentVersion === 'draft' ? 'border-indigo-500' : 'border-gray-300'
                  }`}>
                    {contentVersion === 'draft' && <div className="w-2 h-2 rounded-full bg-indigo-500" />}
                  </div>
                  <span className="text-sm font-medium text-gray-900">初步教案</span>
                  {!hasDraft && <span className="text-xs text-gray-400 ml-1">(未生成)</span>}
                </div>
              </button>
              <button
                onClick={() => setContentVersion('optimized')}
                disabled={!hasOptimized || isGenerating}
                className={`flex-1 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                  contentVersion === 'optimized'
                    ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                } ${!hasOptimized || isGenerating ? 'opacity-40 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    contentVersion === 'optimized' ? 'border-indigo-500' : 'border-gray-300'
                  }`}>
                    {contentVersion === 'optimized' && <div className="w-2 h-2 rounded-full bg-indigo-500" />}
                  </div>
                  <span className="text-sm font-medium text-gray-900">优化教案</span>
                  {!hasOptimized && <span className="text-xs text-gray-400 ml-1">(未生成)</span>}
                </div>
              </button>
            </div>
          </div>

          {/* Info hint */}
          <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200">
            <FileText className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-blue-700">点击生成后可关闭此窗口，AI 将在后台继续排版。完成后页面上方会出现提示，可随时查看和下载。</p>
          </div>

          {/* Error message */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {isGenerating ? '后台继续生成' : '取消'}
          </button>
          <button
            onClick={handleGenerate}
            disabled={isGenerating || (templateType === 'upload' && !templateFile)}
            className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg font-medium text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                生成中...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4" />
                开始生成
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
