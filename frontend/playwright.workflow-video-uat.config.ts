import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const runId =
  process.env.VERIFY_RUN_ID ??
  new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)

process.env.VERIFY_RUN_ID = runId
process.env.VERIFY_RUN_DIR = path.join(repoRoot, 'verification-runs', `workflow-video-uat-${runId}`)

export default defineConfig({
  testDir: './e2e/workflow-video-uat',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: path.join(repoRoot, 'verification-runs', `workflow-video-uat-${runId}`, 'playwright-html') }],
    ['json', { outputFile: path.join(repoRoot, 'verification-runs', `workflow-video-uat-${runId}`, 'results.json') }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'off',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium-workflow-video-uat', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    port: 4173,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
