import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { findTextMatches } from '../src/pdfSearch'
import { runMarkdown } from '../src/report'
import type { Run } from '../src/types'

test('PDF text matching handles split phrases, width variants, and original offsets', () => {
  expect(findTextMatches(['Maximum: ３０', ' MB'], '30 mb')).toEqual([
    [
      { item: 0, start: 9, end: 11 },
      { item: 1, start: 1, end: 3 },
    ],
  ])
  expect(findTextMatches(['原始', '文件文字'], '原始文件')).toEqual([
    [
      { item: 0, start: 0, end: 2 },
      { item: 1, start: 0, end: 2 },
    ],
  ])
  expect(findTextMatches(['no match'], '  ')).toEqual([])
})

test('real PDF search, selection, zoom, live answer, clipboard, Markdown, and mobile tools', async ({
  page,
  context,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await page
    .locator('input[type=file]')
    .setInputFiles(
      fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
    )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await page.getByLabel('Search PDF text', { exact: true }).fill('30 MB')
  await expect(page.locator('.pdf-search-count')).toHaveText(/1 \/ [1-9]/)
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  const match = page.locator('.pdf-search-hit.active').first()
  await expect(match).toBeVisible()
  await expect(match).toHaveText('30 MB')
  const fitWidth = await page
    .locator('.pdf-paper > canvas')
    .evaluate((el) => el.getBoundingClientRect().width)
  await page.getByLabel('PDF zoom', { exact: true }).selectOption('1.5')
  await expect
    .poll(() =>
      page.locator('.pdf-paper > canvas').evaluate((el) => el.getBoundingClientRect().width),
    )
    .toBeGreaterThan(fitWidth)
  await expect(match).toBeVisible()
  const rect = await match.boundingBox()
  expect(rect).not.toBeNull()
  await page.mouse.move(rect!.x + 1, rect!.y + rect!.height / 2)
  await page.mouse.down()
  await page.mouse.move(rect!.x + rect!.width - 1, rect!.y + rect!.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString())).toContain('30 MB')
  await page.getByLabel('Search PDF text', { exact: true }).fill('Cedar')
  await expect(page.locator('.pdf-search-count')).toHaveText(/1 \/ \d+/)
  expect(
    Number((await page.locator('.pdf-search-count').textContent())!.split('/')[1]),
  ).toBeGreaterThan(1)
  await page.getByRole('button', { name: 'Next match', exact: true }).click()
  await expect(page.locator('.pdf-search-count')).toHaveText(/2 \//)
  await page.getByLabel('Search PDF text', { exact: true }).fill('not-in-the-field-guide')
  await expect(page.locator('.pdf-search-count')).toHaveText('No matches')
  await expect(page.locator('.pdf-search-hit')).toHaveCount(0)
  await page.getByLabel('Search PDF text', { exact: true }).press('Escape')
  await page.getByLabel('PDF zoom', { exact: true }).selectOption('fit')
  await page
    .getByLabel('Question', { exact: true })
    .fill('What is the maximum upload size for the Cedar pilot?')
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('query-progress')).toBeVisible()
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  await expect(page.getByTestId('query-progress')).not.toBeVisible()
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
  await expect(page.locator('.evidence-box').first()).toBeVisible()
  await page.getByRole('button', { name: 'Copy answer & sources' }).click()
  await expect(
    page.getByRole('status').filter({ hasText: 'Answer and sources copied.' }),
  ).toBeVisible()
  const clipboard = await page.evaluate(() => navigator.clipboard.readText())
  expect(clipboard).toContain('30 MB')
  expect(clipboard).toContain('ragglass-field-guide.pdf · p. 2')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download Markdown' }).click()
  const file = await download
  expect(file.suggestedFilename()).toMatch(/^ragglass-run-.*\.md$/)
  const markdown = await readFile((await file.path())!, 'utf8')
  expect(markdown).toContain('## Answer')
  expect(markdown).toContain('30 MB')
  expect(markdown).toMatch(/\/api\/documents\/[a-f0-9-]+\/pdf#page=2/)
  expect(markdown).toContain('Measured timings')
  await page.locator('.results-scroll').evaluate((el) => (el.scrollTop = 0))
  await page.getByLabel('Search PDF text', { exact: true }).fill('30 MB')
  await expect(page.locator('.pdf-search-count')).toHaveText(/1 \//)
  await page.screenshot({ path: '../.data/usability-workbench.png', fullPage: true })
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByLabel('搜尋 PDF 文字', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '複製答案與來源' })).toBeVisible()
  await page.getByRole('button', { name: '複製答案與來源' }).click()
  await expect(page.locator('.global-notice')).toContainText('已複製答案與來源')
  await page.locator('.results-scroll').evaluate((el) => (el.scrollTop = 0))
  await page.screenshot({ path: '../.data/usability-workbench.zh-TW.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByLabel('PDF 縮放', { exact: true }).selectOption('3')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.getByLabel('PDF 縮放', { exact: true }).selectOption('fit')
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document.querySelector('.pdf-paper > canvas')!.getBoundingClientRect().width <=
          document.querySelector('.pdf-scroll')!.clientWidth - 40,
      ),
    )
    .toBe(true)
  await page.getByLabel('搜尋 PDF 文字', { exact: true }).fill('30 MB')
  await expect(page.locator('.pdf-search-count')).toHaveText(/1 \//)
  await page.screenshot({ path: '../.data/usability-mobile.zh-TW.png', fullPage: true })
  expect(errors).toEqual([])
})

test('synthetic query UI reconnects, resumes on reload, and stops without a new query', async ({
  page,
  request,
}) => {
  // Explicit UI contract fixture: model/HTTP responses here are synthetic, not live inference.
  const docs = await (await request.get('/api/documents')).json()
  const doc = docs.find(
    (item: { filename: string }) => item.filename === 'ragglass-field-guide.pdf',
  )
  const run: Run = {
    id: '8dbfa4de-7c45-4b0e-8186-c7d82a5cdd5d',
    created_at: new Date().toISOString(),
    status: 'running',
    stage: 'generation',
    question: 'Explicit synthetic UI lifecycle fixture',
    document_ids: [doc.id],
    answer: null,
    answerable: false,
    citations: [],
    evidence: [],
    error: null,
    error_code: null,
    timings_ms: {},
    settings: {
      llm: { model: 'synthetic-fixture', provider: 'fixture' },
      retrieval: { top_k: 5, score_threshold: 0.7 },
    },
  }
  let starts = 0
  let polls = 0
  await page.route('**/api/query/start', (route) => {
    starts++
    return route.fulfill({ status: 202, json: run })
  })
  await page.route(`**/api/runs/${run.id}`, (route) => {
    polls++
    if (polls === 1) return route.abort('connectionrefused')
    if (run.cancel_requested) run.status = run.stage = 'cancelled'
    return route.fulfill({ json: run })
  })
  await page.route(`**/api/runs/${run.id}/cancel`, (route) => {
    run.cancel_requested = true
    return route.fulfill({ json: run })
  })
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await page.getByLabel('Question', { exact: true }).fill(run.question)
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('query-progress')).toContainText('Reconnecting')
  await page.reload()
  await expect(page.getByLabel('Question', { exact: true })).toHaveValue(run.question)
  await expect(page.getByTestId('query-progress')).toContainText('Generation')
  await expect(page.getByRole('button', { name: 'Download Markdown' })).toBeDisabled()
  await page.getByRole('button', { name: 'Stop query', exact: true }).click()
  await expect(page.getByTestId('query-progress')).not.toBeVisible()
  await expect(page.locator('.results-scroll')).toContainText('Query stopped.')
  await expect(page.getByTestId('answer')).not.toBeVisible()
  expect(starts).toBe(1)
  expect(await page.evaluate(() => sessionStorage.getItem('ragglass-active-run'))).toBeNull()
})

test('Markdown renders hostile text literally and does not link deleted sources', () => {
  const run = {
    id: 'synthetic-export',
    created_at: '2026-10-04T00:00:00Z',
    status: 'completed',
    question: '<script>alert(1)</script>',
    answer: '[unsafe](javascript:alert(1))',
    settings: { llm: { model: 'fixture', provider: 'fixture' } },
    timings_ms: { total: 12.34 },
    citations: [
      { document_id: 'removed', filename: '<img>.pdf', pages: [2], source_available: false },
    ],
  } as Run
  const report = runMarkdown(run, 'zh-TW', 'http://127.0.0.1:8000')
  expect(report).toContain('\\<script\\>')
  expect(report).toContain('\\[unsafe\\]\\(javascript:alert\\(1\\)\\)')
  expect(report).toContain('原始 PDF 已刪除')
  expect(report).not.toContain('/api/documents/removed/pdf')
  expect(report).toContain('12.34 ms')
})
