/**
 * TC-P1 · S2 incremental dispatch mock E2E (2/3 capture → dispatch one topic).
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
const RUN_TAG = `dispatch-${Date.now()}`
const RUN_LABEL = `增量派发 ${RUN_TAG}`

test.beforeEach(async ({ page }) => {
  await installWorkflowVideoMockApi(page)
})

test('2/3 capture: copy lead dispatches one topic and author receives script task', async ({ page }) => {
  resetVideoMockForMultiAccount(RUN_LABEL)
  videoMockState.aggregateMode = 'streaming'
  videoMockState.captureSubmitted.add('task-capture-a')
  videoMockState.captureSubmitted.add('task-capture-b')

  await loginAs(page, VIDEO_DEMO_ACCOUNTS.copyLead, PASSWORD)
  await page.goto('/task-center?filter=tracking')
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible({ timeout: 30_000 })

  const rootRow = page.getByTestId('task-center-tracking-panel').getByText(RUN_LABEL).first()
  await expect(rootRow).toBeVisible({ timeout: 30_000 })
  await rootRow.click()

  await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/已收到 2 \/ 3 份采集/)).toBeVisible({ timeout: 15_000 })

  const dispatchResp = page.waitForResponse(
    (r) => /\/dispatch-topic\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
    { timeout: 60_000 },
  )
  await page.getByTestId('video-tracking-dispatch').first().click()
  await dispatchResp

  await expect(page.getByText('已派发').first()).toBeVisible({ timeout: 15_000 })

  await page.getByText('退出登录', { exact: true }).first().click()
  await expect(page.getByTestId('login-form')).toBeVisible({ timeout: 30_000 })

  await loginAs(page, VIDEO_DEMO_ACCOUNTS.copyA, PASSWORD)
  await page.goto('/task-center?filter=inbox')
  await expect(page.getByTestId('task-center-inbox-panel')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('task-center-inbox-panel').getByText(/撰写脚本/).first()).toBeVisible({
    timeout: 30_000,
  })
})
