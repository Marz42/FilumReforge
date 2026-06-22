import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const configDir = path.dirname(fileURLToPath(import.meta.url))
const repoBrowsersPath = path.resolve(configDir, '..', '.playwright-browsers')
const localChrome = path.join(repoBrowsersPath, 'chromium-1217', 'chrome-win64', 'chrome.exe')

if (!process.env.PLAYWRIGHT_BROWSERS_PATH && fs.existsSync(repoBrowsersPath)) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = repoBrowsersPath
}

const chromiumLaunchOptions = fs.existsSync(localChrome) ? { executablePath: localChrome } : {}
const useSystemChromeChannel =
  !fs.existsSync(localChrome) && process.platform === 'win32' && !process.env.CI
const chromiumUseOptions = useSystemChromeChannel
  ? { channel: 'chrome' as const }
  : { launchOptions: chromiumLaunchOptions }

const devPort = Number(process.env.PLAYWRIGHT_DEV_PORT ?? 4173)

export default defineConfig({
  testDir: './e2e',
  testMatch: [
    '**/login.spec.ts',
    '**/task-center.spec.ts',
    '**/task-center-stats.spec.ts',
    '**/task-center-extended.spec.ts',
    '**/task-center-interactions.spec.ts',
    '**/shell.spec.ts',
    '**/settings.spec.ts',
    '**/graph-template-designer.spec.ts',
    '**/workflow-video-v1.spec.ts',
  ],
  testIgnore: ['live/**', 'docker-gui-verification/**', 'workflow-video-uat/**'],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${devPort}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
    ...chromiumUseOptions,
  },
  projects: [
    {
      name: 'chromium',
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