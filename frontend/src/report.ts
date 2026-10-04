import type { Citation, Run } from './types'

const words = (locale: string) =>
  locale === 'en'
    ? {
        question: 'Question',
        answer: 'Answer',
        sources: 'Sources',
        missing: 'Original PDF deleted',
        none: 'No validated citations',
        noAnswer: 'No answer was produced',
        settings: 'Run details',
        timings: 'Measured timings',
        status: 'Status',
        model: 'Model',
        created: 'Created',
        error: 'Error',
        topK: 'Retrieved chunk limit',
        threshold: 'Minimum retrieval score',
        limitation:
          'Citation IDs are validated against retrieved evidence; semantic correctness is not guaranteed. PDF links require this workspace.',
      }
    : {
        question: '問題',
        answer: '答案',
        sources: '來源',
        missing: '原始 PDF 已刪除',
        none: '沒有已驗證的引用',
        noAnswer: '未產生回答',
        settings: '執行資訊',
        timings: '實測耗時',
        status: '狀態',
        model: '模型',
        created: '建立時間',
        error: '錯誤',
        topK: '檢索片段上限',
        threshold: '最低檢索分數',
        limitation:
          '引用 ID 已對照本次檢索證據驗證，仍需核對答案的語意正確性。PDF 連結需透過原工作空間開啟。',
      }

const sourceLabel = (citation: Citation, locale: string) =>
  `${citation.filename} · p. ${citation.pages.join(', ')}${citation.source_available === false ? ` (${words(locale).missing})` : ''}`

// Export untrusted PDF/model text as literal Markdown, including HTML and link syntax.
const literal = (text: string) => text.replace(/[\\`*_{}[\]()<>#+!|~]/g, '\\$&')

export function answerText(run: Run, locale: string): string {
  const t = words(locale)
  const sources = run.citations.map((citation, i) => `[${i + 1}] ${sourceLabel(citation, locale)}`)
  return `${run.answer || t.noAnswer}\n\n${t.sources}\n${sources.join('\n') || t.none}`
}

export function runMarkdown(run: Run, locale: string, origin: string): string {
  const t = words(locale)
  const sources = run.citations.map((citation, i) => {
    const label = literal(sourceLabel(citation, locale))
    if (citation.source_available === false) return `${i + 1}. ${label}`
    const links = citation.pages.map((page) => {
      const url = new URL(`/api/documents/${encodeURIComponent(citation.document_id)}/pdf`, origin)
      url.hash = `page=${page}`
      return `[p. ${page}](${url.href})`
    })
    return `${i + 1}. ${label} — ${links.join(', ')}`
  })
  const details = [
    `- Run ID: ${literal(run.id)}`,
    `- ${t.created}: ${literal(run.created_at)}`,
    `- ${t.status}: ${literal(run.status)}`,
    `- ${t.model}: ${literal(run.settings.llm.model)} (${literal(run.settings.llm.provider)})`,
  ]
  const retrieval = run.settings.retrieval as
    | { top_k?: number; score_threshold?: number }
    | undefined
  if (typeof retrieval?.top_k === 'number') details.push(`- ${t.topK}: ${retrieval.top_k}`)
  if (typeof retrieval?.score_threshold === 'number')
    details.push(`- ${t.threshold}: ${retrieval.score_threshold}`)
  if (run.error) details.push(`- ${t.error}: ${literal(run.error)}`)
  const timings = Object.entries(run.timings_ms).map(
    ([stage, value]) => `- ${literal(stage)}: ${value.toFixed(2)} ms`,
  )
  return [
    '# RAGGlass',
    `## ${t.question}\n\n${literal(run.question)}`,
    `## ${t.answer}\n\n${literal(run.answer || t.noAnswer)}`,
    `## ${t.sources}\n\n${sources.join('\n') || t.none}`,
    `## ${t.settings}\n\n${details.join('\n')}`,
    `## ${t.timings}\n\n${timings.join('\n')}`,
    `*${t.limitation}*`,
    '',
  ].join('\n\n')
}
