import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

import baseConfig from './playwright.config.ts'

const configDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(configDir, '..')
const runId =
  process.env.VERIFY_RUN_ID ??
  new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)

process.env.VERIFY_RUN_ID = runId
process.env.VERIFY_RUN_DIR = path.join(repoRoot, 'verification-runs', `task-center-e2e-${runId}`)

export default defineConfig({
  ...baseConfig,
  testMatch: [
    '**/task-center*.spec.ts',
    '**/workflow-video-v1.spec.ts',
    '**/workflow-video-uat/workflow-video-multi-account-mock.spec.ts',
  ],
  testIgnore: ['live/**', 'docker-gui-verification/**'],
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['list'],
    [
      'html',
      {
        open: 'never',
        outputFolder: path.join(repoRoot, 'verification-runs', `task-center-e2e-${runId}`, 'playwright-html'),
      },
    ],
    [
      'json',
      {
        outputFile: path.join(repoRoot, 'verification-runs', `task-center-e2e-${runId}`, 'results.json'),
      },
    ],
  ],
  projects: [
    {
      name: 'chromium-task-center',
      use: { ...devices['Desktop Chrome'], ...(baseConfig.use?.launchOptions ? { launchOptions: baseConfig.use.launchOptions } : {}) },
    },
  ],
})
