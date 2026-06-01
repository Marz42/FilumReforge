import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const runId =
  process.env.VERIFY_RUN_ID ??
  new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)

process.env.VERIFY_RUN_ID = runId
process.env.VERIFY_RUN_DIR = path.join(repoRoot, 'verification-runs', `workflow-video-live-${runId}`)

const liveBaseURL = process.env.PLAYWRIGHT_LIVE_BASE_URL || 'http://127.0.0.1:38080'

export default defineConfig({
  testDir: './e2e/live',
  testMatch: 'workflow-video-multi-account-live.spec.ts',
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    [
      'html',
      {
        open: 'never',
        outputFolder: path.join(repoRoot, 'verification-runs', `workflow-video-live-${runId}`, 'playwright-html'),
      },
    ],
    [
      'json',
      {
        outputFile: path.join(repoRoot, 'verification-runs', `workflow-video-live-${runId}`, 'results.json'),
      },
    ],
  ],
  globalSetup: './e2e/live/global-setup.mjs',
  globalTeardown: './e2e/live/global-teardown.mjs',
  use: {
    baseURL: liveBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'off',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium-video-live', use: { ...devices['Desktop Chrome'] } }],
})
