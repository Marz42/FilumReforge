import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const repoBrowsersPath = path.resolve(repoRoot, '.playwright-browsers')
const localChrome = path.join(repoBrowsersPath, 'chromium-1217', 'chrome-win64', 'chrome.exe')
const runId =
  process.env.VERIFY_RUN_ID ??
  new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)
const devPort = Number(process.env.PLAYWRIGHT_DEV_PORT ?? 4173)

if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(repoBrowsersPath)) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = repoBrowsersPath
}

process.env.VERIFY_RUN_ID = runId
process.env.VERIFY_RUN_DIR = path.join(repoRoot, 'verification-runs', `workflow-video-live-${runId}`)

const chromiumLaunchOptions = fs.existsSync(localChrome) ? { executablePath: localChrome } : {}
const useSystemChromeChannel =
  !fs.existsSync(localChrome) && process.platform === 'win32' && !process.env.CI
const chromiumUseOptions = useSystemChromeChannel
  ? { channel: 'chrome' as const }
  : { launchOptions: chromiumLaunchOptions }

export default defineConfig({
  testDir: './e2e/workflow-video-uat',
  testMatch: 'workflow-video-multi-account-mock.spec.ts',
  timeout: 120_000,
  expect: { timeout: 15_000 },
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
  use: {
    baseURL: `http://127.0.0.1:${devPort}`,
    trace: 'retain-on-failure',
    screenshot: 'off',
    video: 'off',
    ...chromiumUseOptions,
  },
  projects: [
    {
      name: 'chromium-video-multi-mock',
      use: { ...devices['Desktop Chrome'], ...chromiumUseOptions },
    },
  ],
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${devPort}`,
    port: devPort,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
