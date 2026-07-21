/**
 * Shared mapping of `export_records.source_kind` raw values → friendly
 * Chinese labels.
 *
 * Used by:
 * - `AdminUserExports.tsx` (admin per-user export audit table)
 * - `DocumentsLibrary.tsx` (user-facing "我的导出" tab tag + filter)
 * - `ZhukeHistory.tsx` (dedicated zhuke history page)
 *
 * Unknown kinds fall through verbatim via `humanizeSourceKind`, so adding a
 * new export kind without updating this file never loses information — only
 * loses the pretty label.
 */
export const SOURCE_KIND_LABELS: Record<string, string> = {
  lesson: '教案',
  lesson_optimized: '优化稿',
  lesson_draft: '教案草稿',
  course_tool: '课程工具',
  bundle: '批量打包',
  template_fill: '模板填写',
  styled_pdf: '美化版 PDF',
  material_draft: '教材草稿',
  material_optimized: '教材优化稿',
  zhuke_generation: '珠科教案生成',
  zhuke_lesson: '珠科教案下载',
}

/** Returns the friendly label for a `source_kind`, falling back to the raw value. */
export function humanizeSourceKind(k: string): string {
  if (!k) return ''
  return SOURCE_KIND_LABELS[k] ?? k
}

/** Stable list of `[value, label]` pairs for building dropdowns in source_kind filters. */
export function sourceKindOptions(): Array<{ value: string; label: string }> {
  return Object.entries(SOURCE_KIND_LABELS).map(([value, label]) => ({ value, label }))
}
