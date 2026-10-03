/** Capture the actual bilingual UI using the public fixture and live inference. */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = new URL('../', import.meta.url)
process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(new URL('.cache/playwright', root))
const require = createRequire(new URL('frontend/package.json', root))
const { chromium, expect } = require('@playwright/test')
const baseURL = process.env.RAGGLASS_BASE_URL || 'http://127.0.0.1:8000'
const fixture = new URL('examples/ragglass-field-guide.pdf', root)
const hash = createHash('sha256')
  .update(await readFile(fixture))
  .digest('hex')
const allowedQuestions = new Set([
  ...JSON.parse(await readFile(new URL('examples/questions.json', root), 'utf8')).map(
    (item) => item.question,
  ),
  'Cedar 試用方案的上傳容量上限是多少？',
])
const documents = await (await fetch(new URL('/api/documents', baseURL))).json()
const runs = await (await fetch(new URL('/api/runs', baseURL))).json()
const fixtureIds = new Set(documents.map((item) => item.id))
if (
  documents.some((item) => item.hash !== hash) ||
  runs.some(
    (item) =>
      !allowedQuestions.has(item.question) || item.document_ids.some((id) => !fixtureIds.has(id)),
  )
) {
  throw new Error(
    'Capture requires a workspace containing only the public fixture and sample questions.',
  )
}
const output = fileURLToPath(new URL('docs/images/', root))
await mkdir(output, { recursive: true })
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === 'chromium' ? undefined : 'chrome',
})
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
page.setDefaultTimeout(180_000)
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
const records = []
try {
  for (const language of ['en', 'zh-TW']) {
    await page.goto(baseURL)
    await page.getByLabel('Language').selectOption(language)
    await page
      .locator('input[type=file]')
      .setInputFiles(fileURLToPath(new URL('examples/ragglass-field-guide.pdf', root)))
    await expect(page.locator('.document-bar .badge')).toHaveText(
      language === 'en' ? 'Indexed' : '已索引',
      { timeout: 180_000 },
    )
    const question =
      language === 'en'
        ? 'What is the maximum upload size for the Cedar pilot?'
        : 'Cedar 試用方案的上傳容量上限是多少？'
    await page.getByLabel('Question', { exact: true }).fill(question)
    const response = page.waitForResponse(
      (r) => r.url().endsWith('/api/query') && r.request().method() === 'POST',
    )
    await page
      .getByRole('button', {
        name: language === 'en' ? 'Retrieve & answer' : '檢索並回答',
      })
      .click()
    const run = await (await response).json()
    if (run.status !== 'completed' || !run.answerable || !run.citations.length) {
      throw new Error(`Live query failed: ${run.error_code || run.status}`)
    }
    await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
    await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
    await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
    await expect(page.locator('.pdf-loading')).not.toBeVisible()
    await expect(page.locator('.evidence-box').first()).toBeVisible()
    const suffix = language === 'en' ? '' : '.zh-TW'
    await page.screenshot({ path: `${output}/workbench${suffix}.png`, fullPage: true })
    await page.getByTestId('open-library').click()
    await page.screenshot({ path: `${output}/document-library${suffix}.png`, fullPage: true })
    await page.keyboard.press('Escape')
    await page
      .getByRole('tab', {
        name: language === 'en' ? 'Parsed content' : '解析內容',
        exact: true,
      })
      .click()
    await page
      .locator('.parsed-chunk')
      .filter({ hasText: '30 MB' })
      .first()
      .scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${output}/parsed-content${suffix}.png`, fullPage: true })
    await page
      .getByRole('tab', {
        name: language === 'en' ? 'Original PDF' : '原始 PDF',
        exact: true,
      })
      .click()
    await page.getByTestId('open-history').click()
    await page.screenshot({ path: `${output}/run-history${suffix}.png`, fullPage: true })
    await page.keyboard.press('Escape')
    await page.locator('.run-details > summary').click()
    await page.locator('.run-details').scrollIntoViewIfNeeded()
    await page.screenshot({ path: `${output}/run-settings${suffix}.png`, fullPage: true })
    records.push({
      language,
      question,
      run_id: run.id,
      model: run.settings.llm.model,
      timings_ms: run.timings_ms,
      mock: false,
    })
    console.log(`Captured five actual ${language} screens with ${run.settings.llm.model}`)
  }
  if (errors.length) throw new Error(errors.join('\n'))
  await mkdir(fileURLToPath(new URL('.data/', root)), { recursive: true })
  await writeFile(
    fileURLToPath(new URL('.data/ui-docs-capture.json', root)),
    JSON.stringify(records, null, 2) + '\n',
  )
} finally {
  await browser.close()
}
