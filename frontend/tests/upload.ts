import { expect, type Page } from '@playwright/test'

export async function uploadPdf(page: Page, filename: string) {
  const accepted = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/api/documents' &&
      response.request().method() === 'POST',
  )
  await page.locator('input[type=file]').setInputFiles(filename)
  const response = await accepted
  expect(response.status()).toBe(202)
  const document = await response.json()
  await expect(page.locator('.document-switcher select')).toHaveValue(document.id)
  await expect(page.getByTestId('upload-status')).not.toBeVisible()
  return document
}
