import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

test('real PDF upload, live model answer, page citation, history, and language persistence', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await expect(page.getByRole('heading', { name: 'Document workbench', exact: true })).toBeVisible()
  await page
    .locator('input[type=file]')
    .setInputFiles(
      fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
    )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '1')
  await expect(page.locator('canvas')).toBeVisible()
  await page
    .getByLabel('Question', { exact: true })
    .fill('What is the maximum upload size for the Cedar pilot?')
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  await expect(page.getByTestId('answer')).toContainText('30 MB', { timeout: 180_000 })
  const citation = page.locator('.citation-button').filter({ hasText: 'p. 2' }).first()
  await expect(citation).toBeVisible()
  await citation.click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  await expect(page.locator('.evidence-box').first()).toBeVisible()
  await page.screenshot({ path: '../.data/workbench.png', fullPage: true })
  await page.reload()
  await expect(page.getByLabel('Language')).toHaveValue('en')
  await page
    .locator('.history-item')
    .filter({ hasText: 'What is the maximum upload size for the Cedar pilot?' })
    .first()
    .click()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await page.getByRole('button', { name: 'Parsed content', exact: true }).click()
  await expect(page.locator('.parsed-chunk').filter({ hasText: '30 MB' }).first()).toBeVisible()
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByRole('heading', { name: '文件診斷工作台', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})
