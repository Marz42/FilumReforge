import { defineConfig, devices } from '@playwright/test'

const liveBaseURL = process.env.PLAYWRIGHT_LIVE_BASE_URL || 'http://127.0.0.1:38080'

export default defineConfig({
  testDir: './e2e/live',
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  globalSetup: './e2e/live/global-setup.mjs',
  globalTeardown: './e2e/live/global-teardown.mjs',
  use: {
    baseURL: liveBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium-live',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})