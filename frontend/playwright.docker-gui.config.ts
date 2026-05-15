import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const runId =
  process.env.VERIFY_RUN_ID ??
  new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)

process.env.VERIFY_RUN_ID = runId
process.env.VERIFY_RUN_DIR = path.join(repoRoot, 'verification-runs', `docker-gui-${runId}`)

const baseURL = process.env.GUI_BASE_URL ?? 'http://127.0.0.1:8080'

export default defineConfig({
  testDir: './e2e/docker-gui-verification',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'off',
    video: 'off',
    ignoreHTTPSErrors: true,
  },
  projects: [{ name: 'chromium-docker-gui', use: { ...devices['Desktop Chrome'] } }],
})
