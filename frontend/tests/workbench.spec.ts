import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { uploadPdf } from './upload'

test('real PDF upload, live model answer, page citation, history, and language persistence', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await expect(page.getByRole('heading', { name: 'Document workbench', exact: true })).toBeVisible()
  await uploadPdf(
    page,
    fileURLToPath(new URL('../../examples/ragglass-field-guide.pdf', import.meta.url)),
  )
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', { timeout: 180_000 })
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '1')
  await expect(page.locator('.pdf-paper > canvas')).toBeVisible()
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
  await page.getByTestId('open-history').click()
  await expect(page.getByRole('dialog', { name: 'Run history' })).toBeVisible()
  await page
    .locator('.history-item')
    .filter({ hasText: 'What is the maximum upload size for the Cedar pilot?' })
    .first()
    .click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await page.getByRole('tab', { name: 'Parsed content', exact: true }).click()
  await expect(page.locator('.parsed-chunk').filter({ hasText: '30 MB' }).first()).toBeVisible()
  await page.getByLabel('Language').selectOption('zh-TW')
  await expect(page.getByRole('heading', { name: '文件診斷工作台', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('document catalog, page rail, keyboard dismissal, retrieval inputs, and mobile reading', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Language').selectOption('en')
  await page.getByTestId('open-library').click()
  await expect(page.getByRole('dialog', { name: 'Document library' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(page.getByTestId('open-library')).toBeFocused()
  await page.getByTestId('open-library').click()
  await page
    .locator('.document-item')
    .filter({ hasText: 'ragglass-field-guide.pdf' })
    .first()
    .click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.getByRole('button', { name: 'Page 3', exact: true }).click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '3')
  await expect(page.getByRole('button', { name: 'Page 3', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  )
  await expect(page.locator('.pdf-paper > canvas')).toBeVisible()
  await page.getByTestId('open-history').click()
  await page
    .locator('.history-item')
    .filter({ hasText: 'What is the maximum upload size for the Cedar pilot?' })
    .first()
    .click()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await page.locator('.retrieval-options > summary').click()
  await page.getByLabel('Minimum score', { exact: true }).fill('')
  await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeDisabled()
  await page.getByLabel('Question', { exact: true }).press('Control+Enter')
  await page.getByLabel('Minimum score', { exact: true }).fill('0.70')
  await expect(page.getByRole('button', { name: 'Retrieve & answer' })).toBeEnabled()
  await page.locator('.retrieval-options > summary').click()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: 'Document workbench', exact: true })).toBeVisible()
  await expect(page.getByTestId('pdf-viewer')).toBeVisible()
  await expect(page.getByTestId('answer')).toBeVisible()
  await expect
    .poll(() =>
      page.evaluate(() => {
        const viewer = document.querySelector('.pdf-scroll')!
        const canvas = document.querySelector('.pdf-paper > canvas')!
        return canvas.getBoundingClientRect().width <= viewer.clientWidth - 40
      }),
    )
    .toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.screenshot({ path: '../.data/workbench-mobile.png', fullPage: true })
  await page.getByTestId('open-history').click()
  await expect(page.getByRole('dialog', { name: 'Run history' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.keyboard.press('Escape')
  expect(errors).toEqual([])
})
