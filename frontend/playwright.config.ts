import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(
  new URL('../.cache/playwright', import.meta.url),
)

export default defineConfig({
  testDir: './tests',
  timeout: 240_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.RAGGLASS_BASE_URL || 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 1000 },
    channel: process.env.RAGGLASS_BROWSER === 'chromium' ? undefined : 'chrome',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
