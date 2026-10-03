import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'

// Destructive browser checks run only in the disposable server started by verify_cleanup.py.
test('real query, cleanup confirmation, document removal, retained evidence, and history clearing', async ({
  page,
}) => {
  test.skip(
    process.env.RAGGLASS_CLEANUP_TEST !== '1',
    'Requires the isolated cleanup verification server.',
  )
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await page
    .locator('input[type=file]')
    .setInputFiles(
      fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
    )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await expect(page.locator('canvas')).toBeVisible()
  const question = 'What is the maximum upload size for the Cedar pilot?'
  await page.getByLabel('Question', { exact: true }).fill(question)
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')

  await page.getByTestId('open-history').click()
  let catalog = page.getByRole('dialog', { name: 'Run history', exact: true })
  await catalog.getByLabel('Search questions across all records').fill('maximum upload')
  await expect(catalog.locator('.history-item')).toHaveCount(1)
  await catalog.getByRole('button', { name: `Delete ${question}`, exact: true }).click()
  let confirm = page.getByRole('dialog', { name: 'Confirm cleanup', exact: true })
  await expect(confirm).toContainText('PDFs and their indexes remain.')
  await expect(confirm.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await confirm.getByRole('button', { name: 'Cancel' }).click()
  await expect(catalog.locator('.history-item')).toHaveCount(1)
  await catalog.getByRole('button', { name: `Delete ${question}`, exact: true }).click()
  await confirm.getByTestId('confirm-cleanup').click()
  await expect(catalog.locator('.history-item')).toHaveCount(0)
  await catalog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByTestId('answer')).not.toBeVisible()
  await expect(page.getByLabel('Question', { exact: true })).toHaveValue(question)
  await expect(page.locator('canvas')).toBeVisible()

  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  await page.getByTestId('open-library').click()
  catalog = page.getByRole('dialog', { name: 'Document library', exact: true })
  await catalog.getByLabel('Search filenames').fill('ragglass-field-guide')
  await catalog.getByLabel('Filter by status').selectOption('ready')
  await expect(catalog.locator('.document-item')).toHaveCount(1)
  await catalog.getByLabel('Select ragglass-field-guide.pdf', { exact: true }).check()
  const images = fileURLToPath(new URL('../../docs/images/', import.meta.url))
  await mkdir(images, { recursive: true })
  await page.screenshot({ path: `${images}/document-cleanup.png`, fullPage: true })
  await catalog.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByLabel('Language').selectOption('zh-TW')
  await page.getByTestId('open-library').click()
  catalog = page.getByRole('dialog', { name: '文件庫', exact: true })
  await catalog.getByLabel('搜尋檔名').fill('ragglass-field-guide')
  await catalog.getByLabel('依狀態篩選').selectOption('ready')
  await catalog.getByLabel('選取 ragglass-field-guide.pdf', { exact: true }).check()
  await page.screenshot({ path: `${images}/document-cleanup.zh-TW.png`, fullPage: true })
  await catalog.getByTestId('delete-selected').click()
  confirm = page.getByRole('dialog', { name: '確認清理', exact: true })
  await expect(confirm).toContainText('執行紀錄仍保留')
  await confirm.getByTestId('confirm-cleanup').click()
  await expect(catalog.locator('.document-item')).toHaveCount(0)
  await catalog.getByRole('button', { name: '關閉', exact: true }).click()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await expect(page.locator('canvas')).not.toBeVisible()
  await expect(page.locator('.missing-source')).toContainText('原始 PDF 已刪除')
  await expect(page.locator('.citation-button').first()).toBeDisabled()
  await page.locator('.evidence-card').first().click()
  await expect(page.locator('.evidence-card').first()).toHaveAttribute('aria-expanded', 'true')

  await page.getByTestId('open-history').click()
  catalog = page.getByRole('dialog', { name: '執行紀錄', exact: true })
  await expect(catalog.locator('.history-item')).toHaveCount(1)
  await page.screenshot({ path: `${images}/history-cleanup.zh-TW.png`, fullPage: true })
  await catalog.getByRole('button', { name: '關閉', exact: true }).click()
  await page.getByLabel('Language').selectOption('en')
  await page.getByTestId('open-history').click()
  catalog = page.getByRole('dialog', { name: 'Run history', exact: true })
  await expect(catalog.locator('.history-item')).toHaveCount(1)
  await page.screenshot({ path: `${images}/history-cleanup.png`, fullPage: true })
  await catalog.locator('.history-item').click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await page.reload()
  await expect(page.getByLabel('Language')).toHaveValue('en')
  await page.getByTestId('open-history').click()
  catalog = page.getByRole('dialog', { name: 'Run history', exact: true })
  await expect(catalog.locator('.history-item')).toHaveCount(1)
  await page.setViewportSize({ width: 390, height: 844 })
  await catalog.getByTestId('clear-all').click()
  confirm = page.getByRole('dialog', { name: 'Confirm cleanup', exact: true })
  await expect(confirm).toContainText('including items hidden by filters or pagination')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await confirm.getByTestId('confirm-cleanup').click()
  await expect(catalog.locator('.history-item')).toHaveCount(0)
  await expect(page.getByTestId('open-history')).toContainText('0')
  await page.reload()
  await expect(page.locator('canvas')).not.toBeVisible()
  await page.getByTestId('open-history').click()
  await expect(page.locator('.history-item')).toHaveCount(0)
  expect(errors).toEqual([])
  await writeFile(
    fileURLToPath(new URL('../../.data/cleanup-browser.json', import.meta.url)),
    JSON.stringify(
      {
        mock: false,
        live_queries: 2,
        errors,
        checks: [
          'cancel preserves data',
          'run delete preserves PDF and question',
          'document delete removes PDF and preserves history',
          'missing PDF citation disabled',
          'saved evidence expands',
          'history reopens after document deletion',
          'clear all and reload',
          '390px confirmation',
        ],
        screenshots: [
          'document-cleanup.png',
          'document-cleanup.zh-TW.png',
          'history-cleanup.png',
          'history-cleanup.zh-TW.png',
        ],
      },
      null,
      2,
    ),
  )
})
