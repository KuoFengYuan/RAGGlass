import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { uploadPdf } from './upload'

test('real generation controls, context/native usage trace, and history settings', async ({
  page,
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
  await page.getByTestId('generation-controls').locator('summary').click()
  await page.getByRole('button', { name: 'Varied phrasing', exact: true }).click()
  await expect(page.getByLabel('Temperature', { exact: true })).toHaveValue('0.8')
  await page.getByLabel('Top P', { exact: true }).fill('0')
  await page
    .getByLabel('Question', { exact: true })
    .fill('What is the maximum upload size for the Cedar pilot? Answer briefly.')
  await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeDisabled()
  await page.getByLabel('Temperature', { exact: true }).fill('0.2')
  await page.getByLabel('Top P', { exact: true }).fill('0.9')
  await page.getByLabel('Output token limit', { exact: true }).fill('512')
  const submitted = page.waitForResponse(
    (response) => response.url().endsWith('/api/query/start') && response.status() === 202,
  )
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  const start = await (await submitted).json()
  expect(start.settings.llm.temperature).toBe(0.2)
  expect(start.settings.llm.top_p).toBe(0.9)
  expect(start.settings.llm.max_tokens).toBe(512)
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  await expect(page.getByTestId('workflow-trace')).toContainText('Estimated input')
  await expect(page.getByTestId('model-usage')).toContainText('1 reported calls')
  await page.getByRole('button', { name: 'Precise phrasing', exact: true }).click()
  await page.getByTestId('open-history').click()
  await page.locator('.history-item').filter({ hasText: 'Answer briefly.' }).first().click()
  await expect(page.getByLabel('Temperature', { exact: true })).toHaveValue('0.2')
  await expect(page.getByLabel('Top P', { exact: true })).toHaveValue('0.9')
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByTestId('workflow-trace')).toContainText('實際回報輸入／輸出')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '../.data/workflows-controls.zh-TW.png', fullPage: true })
  expect(errors).toEqual([])
})

test('real three-point document summary, source navigation, node trace, and reload', async ({
  page,
  request,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  const target = process.env.RAGGLASS_SUMMARY_DOCUMENT_ID
  if (target) {
    await page.getByLabel('Active document').selectOption(target)
  } else {
    await uploadPdf(
      page,
      fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
    )
  }
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  const submitted = page.waitForResponse(
    (response) => response.url().endsWith('/api/summary/start') && response.status() === 202,
  )
  await page.getByRole('button', { name: 'Summarize document in 3 points', exact: true }).click()
  const start = await (await submitted).json()
  await expect(page.getByTestId('query-progress')).toBeVisible()
  await expect(page.getByTestId('answer')).toBeVisible({ timeout: 180_000 })
  const run = await (await request.get(`/api/runs/${start.id}`)).json()
  expect(run.status).toBe('completed')
  expect(run.summary_points).toHaveLength(3)
  expect(run.workflow.nodes.length).toBeGreaterThanOrEqual(2)
  if (target) expect(run.workflow.map_batches).toBeGreaterThan(1)
  await expect(page.getByTestId('workflow-trace')).toContainText('Document summary steps')
  const citation = page.locator('.citation-button').first()
  const destination = run.citations[0].pages[0]
  await citation.click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', String(destination))
  await page.reload()
  await page.getByTestId('open-history').click()
  await page
    .locator('.history-item')
    .filter({ hasText: 'Three-point document summary' })
    .first()
    .click()
  await expect(page.getByTestId('answer')).toBeVisible()
  await expect(page.getByTestId('workflow-trace')).toContainText('Document summary steps')
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByRole('button', { name: '三點文件摘要', exact: true })).toBeVisible()
  await page.locator('.results-scroll').evaluate((el) => (el.scrollTop = 0))
  await page.screenshot({ path: '../.data/workflows-summary.zh-TW.png', fullPage: true })
  expect(errors).toEqual([])
})
