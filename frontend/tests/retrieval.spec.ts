import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'
import { uploadPdf } from './upload'

test('real modes, candidate limits, score labels, PDF links, history and Markdown', async ({
  page,
  request,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await uploadPdf(
    page,
    fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
  )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await page.locator('.retrieval-options > summary').click()
  await page
    .getByLabel('Question', { exact: true })
    .fill(
      'What is the maximum upload size for the Cedar pilot? Please answer briefly with evidence.',
    )
  await page.getByLabel('Top K', { exact: true }).fill('3')
  for (const mode of ['dense', 'keyword', 'hybrid']) {
    await page.getByLabel('Retrieval mode', { exact: true }).selectOption(mode)
    if (mode === 'keyword')
      await expect(page.getByLabel('Minimum score', { exact: true })).toBeDisabled()
    if (mode === 'hybrid') {
      await page.getByLabel('Candidates per method', { exact: true }).fill('1')
      await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeDisabled()
      await page.getByLabel('Candidates per method', { exact: true }).fill('4')
    }
    const submitted = page.waitForResponse(
      (r) => r.url().endsWith('/api/query/start') && r.status() === 202,
    )
    await page.getByRole('button', { name: 'Retrieve & answer' }).click()
    const start = await (await submitted).json()
    expect(start.settings.retrieval.mode).toBe(mode)
    await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
    await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeEnabled()
    const run = await (await request.get(`/api/runs/${start.id}`)).json()
    expect(run.status).toBe('completed')
    expect(run.evidence.length).toBeLessThanOrEqual(3)
    expect(
      run.evidence.every(
        (e: { score_kind: string }) =>
          e.score_kind ===
          ({ dense: 'cosine', keyword: 'bm25', hybrid: 'rrf' } as Record<string, string>)[mode],
      ),
    ).toBe(true)
    await expect(page.locator('.evidence-card .score').first()).toContainText(
      ({ dense: 'cos', keyword: 'BM25', hybrid: 'RRF' } as Record<string, string>)[mode],
    )
  }
  await page.getByTestId('retrieval-trace').locator('summary').click()
  await expect(page.getByTestId('retrieval-trace')).toContainText('Hybrid uses RRF ranks')
  const citation = page.locator('.citation-button').filter({ hasText: 'p. 2' }).first()
  await citation.click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download Markdown', exact: false }).click()
  const path = await (await downloaded).path()
  const markdown = await readFile(path!, 'utf8')
  expect(markdown).toContain('hybrid-rrf')
  expect(markdown).toContain('Retrieved evidence rankings')
  expect(markdown).toContain('dense #')
  expect(markdown).toContain('keyword #')
  await page.getByLabel('Retrieval mode', { exact: true }).selectOption('dense')
  await page.getByTestId('open-history').click()
  await page
    .locator('.history-item')
    .filter({ hasText: 'Please answer briefly with evidence.' })
    .first()
    .click()
  await expect(page.getByLabel('Retrieval mode', { exact: true })).toHaveValue('hybrid')
  await expect(page.getByLabel('Candidates per method', { exact: true })).toHaveValue('4')
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByTestId('retrieval-trace')).toContainText('檢索排名追蹤')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '../.data/retrieval.zh-TW.png', fullPage: true })
  expect(errors).toEqual([])
})

test('real Chinese keyword retrieval and original PDF text search', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  const target = process.env.RAGGLASS_RETRIEVAL_DOCUMENT_ID
  if (target) await page.getByLabel('Active document').selectOption(target)
  else
    await uploadPdf(
      page,
      fileURLToPath(new URL('../../examples/ragglass-retrieval-lab.pdf', import.meta.url)),
    )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await page.locator('.retrieval-options > summary').click()
  await page.getByLabel('Retrieval mode', { exact: true }).selectOption('keyword')
  await page.getByLabel('Question', { exact: true }).fill('文件庫會保留查詢紀錄幾天？')
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('answer')).toContainText(/90|九十/, { timeout: 180_000 })
  await page.locator('.citation-button').filter({ hasText: 'p. 6' }).first().click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '6')
  await expect(page.locator('.pdf-text-layer')).toContainText('九十天')
  await page.getByPlaceholder('Search this PDF…').fill('九十天')
  await expect(page.locator('.pdf-search-hit.active').first()).toHaveText('九十天')
  expect(errors).toEqual([])
})
