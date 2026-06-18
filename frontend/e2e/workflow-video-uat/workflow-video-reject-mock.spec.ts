/**
 * TC-P1-7 · capture reject mock E2E (manager rejects → editor sees 已退回).
 */

import { expect, test } from '@playwright/test'

import {
  installWorkflowVideoMockApi,
  loginAs,
  resetVideoMockForMultiAccount,
  videoMockState,
  VIDEO_DEMO_ACCOUNTS,
} from '../workflow-video-mock.ts'

const PASSWORD = 'secret-password'
const RUN_LABEL = `reject-${Date.now()}`

test.beforeEach(async ({ page }) => {
  await installWorkflowVideoMockApi(page)
})

test('copy lead rejects submitted capture and editor sees returned state', async ({ page }) => {
  resetVideoMockForMultiAccount(RUN_LABEL)
  videoMockState.captureSubmitted.add('task-capture-a')

  await loginAs(page, VIDEO_DEMO_ACCOUNTS.copyLead, PASSWORD)
  await page.goto('/task-center?filter=tracking')
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible({ timeout: 30_000 })

  await page.getByTestId('task-center-tracking-panel').getByText(RUN_LABEL).first().click()
  await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 30_000 })

  const rejectResp = page.waitForResponse(
    (r) => /\/reject-captures\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
    { timeout: 60_000 },
  )
  await page.getByTestId('video-tracking-reject').first().click()
  await page.getByTestId('video-tracking-reject-reason').fill('选题方向需调整')
  await page.getByRole('button', { name: '确认打回' }).click()
  await rejectResp

  await page.getByText('退出登录', { exact: true }).first().click()
  await expect(page.getByTestId('login-form')).toBeVisible({ timeout: 30_000 })

  await loginAs(page, VIDEO_DEMO_ACCOUNTS.copyA, PASSWORD)
  await page.goto('/task-center?filter=inbox&selected=task-capture-a')
  await expect(page.getByTestId('task-center-inbox-panel')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('tasks-detail-panel').getByText('已退回')).toBeVisible({
    timeout: 30_000,
  })
})
