import { expect, test } from '@playwright/test'
import path from 'node:path'
import type { Document } from '../src/types'
import { uploadPdf } from './upload'

const fixtures = process.env.RAGGLASS_INGESTION_FIXTURES_DIR

test('real local PDF inspection blocks invalid uploads before any upload request', async ({
  page,
}) => {
  test.skip(!fixtures, 'Run via scripts/verify_ingestion.py --browser in a disposable workspace.')
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  let uploads = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/documents')
      uploads++
  })
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await expect(page.getByTestId('upload-limits')).toContainText('30 MB')
  await expect(page.getByTestId('upload-limits')).toContainText('200 pages')
  const input = page.locator('input[type=file]')
  for (const [name, message] of [
    ['invalid.pdf', 'Cannot read this PDF'],
    ['encrypted.pdf', 'encrypted'],
    ['blank.pdf', 'no selectable text'],
    ['too-many-pages.pdf', 'page limit'],
  ]) {
    await input.setInputFiles(path.join(fixtures!, name!))
    await expect(page.getByRole('alert').filter({ hasText: message! })).toBeVisible()
    await expect(page.getByTestId('upload-status')).not.toBeVisible()
  }
  await input.setInputFiles({
    name: 'large.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.alloc(31 * 1024 * 1024),
  })
  await expect(page.getByRole('alert').filter({ hasText: 'size limit' })).toBeVisible()
  expect(uploads).toBe(0)
  await page.getByLabel('Language').selectOption('zh-TW')
  await input.setInputFiles(path.join(fixtures!, 'blank.pdf'))
  await expect(page.getByRole('alert').filter({ hasText: '目前尚未支援 OCR' })).toBeVisible()
  await expect(page.getByTestId('upload-limits')).toContainText('200 頁')
  expect(uploads).toBe(0)
  expect(errors).toEqual([])
})

test('real processing can be stopped, reopened, reindexed, and queried with valid sources', async ({
  page,
}) => {
  test.skip(!fixtures, 'Run via scripts/verify_ingestion.py --browser in a disposable workspace.')
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await uploadPdf(page, path.join(fixtures!, 'browser-native.pdf'))
  await expect(page.getByTestId('document-progress')).toBeVisible()
  await page.getByRole('button', { name: 'Stop processing', exact: true }).click()
  await expect(page.getByTestId('document-progress')).toContainText('Processing stopped', {
    timeout: 180_000,
  })
  await expect(page.getByTestId('document-progress')).toContainText('Original PDF')
  await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeDisabled()
  await page.reload()
  await expect(page.getByTestId('document-progress')).toContainText('Processing stopped')
  await page.getByRole('button', { name: 'Reindex' }).click()
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await expect(page.getByTestId('document-progress')).not.toBeVisible()
  await page
    .getByLabel('Question', { exact: true })
    .fill('What is the maximum upload size for the Cedar pilot?')
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  await uploadPdf(page, path.join(fixtures!, 'browser-native.pdf'))
  await expect(page.locator('.global-notice')).toContainText('already in the document library')
  await page.getByTestId('open-library').click()
  await expect(page.getByRole('dialog', { name: 'Document library' })).toContainText('200 pages')
  await page.keyboard.press('Escape')
  await page.getByLabel('Language').selectOption('zh-TW')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByTestId('upload-limits')).toContainText('200 頁')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '../.data/ingestion-mobile.png', fullPage: true })
  expect(errors).toEqual([])
})

test('synthetic document progress survives reload and shows stop acknowledgement in both languages', async ({
  page,
  request,
}) => {
  test.skip(!fixtures, 'Run via scripts/verify_ingestion.py --browser in a disposable workspace.')
  // Explicit UI contract: document metadata/cancellation are mocked, PDF bytes stay real.
  const documents: Document[] = await (await request.get('/api/documents')).json()
  const source = documents.find((document) => document.status === 'ready')!
  expect(source).toBeTruthy()
  let current: Document = {
    ...source,
    status: 'embedding',
    queued_at: new Date(Date.now() - 10_000).toISOString(),
    processing_started_at: new Date(Date.now() - 8000).toISOString(),
    finished_at: null,
    cancel_requested: false,
    progress: { total_chunks: 12, embedded_chunks: 8, indexed_chunks: 4 },
  }
  let stops = 0
  await page.route('**/api/documents', (route) => route.fulfill({ json: [current] }))
  await page.route(`**/api/documents/${source.id}/cancel`, (route) => {
    stops++
    current = { ...current, cancel_requested: true }
    return route.fulfill({ json: current })
  })
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await expect(page.getByTestId('document-progress')).toContainText('Embedded 8 / 12')
  await expect(page.getByTestId('document-progress')).toContainText('Indexed 4 / 12')
  await expect(page.getByRole('progressbar', { name: 'Chunks written to index' })).toHaveAttribute(
    'value',
    '4',
  )
  await page.reload()
  await expect(page.getByTestId('document-progress')).toContainText('Elapsed')
  await page.getByRole('button', { name: 'Stop processing', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Stopping…', exact: true })).toBeDisabled()
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByTestId('document-progress')).toContainText('等待目前操作完成後停止')
  await expect(page.getByRole('button', { name: '正在停止…', exact: true })).toBeDisabled()
  current = { ...current, status: 'cancelled', finished_at: new Date().toISOString() }
  await expect(page.getByTestId('document-progress')).toContainText('處理已停止')
  await expect(page.getByRole('button', { name: '重新索引' })).toBeEnabled()
  await expect(page.getByRole('button', { name: '停止處理', exact: true })).not.toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  expect(stops).toBe(1)
})
