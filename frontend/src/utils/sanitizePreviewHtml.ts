/**
 * AI 生成的 HTML 在 iframe srcDoc 中展示时，可能包含嵌套 iframe、base、meta refresh
 * 指向 localhost 等，导致子框架加载失败（chrome-error://）并触发浏览器跨域安全报错。
 */
export function sanitizePreviewHtml(html: string): string {
  if (!html) return ''
  let s = html
  s = s.replace(/<base\b[^>]*>/gi, '')
  s = s.replace(/<meta\b[^>]*http-equiv\s*=\s*["']?\s*refresh["']?[^>]*>/gi, '')
  for (let i = 0; i < 8; i++) {
    const next = s
      .replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, '')
      .replace(/<iframe\b[^>]*\/?>/gi, '')
    if (next === s) break
    s = next
  }
  return s
}
