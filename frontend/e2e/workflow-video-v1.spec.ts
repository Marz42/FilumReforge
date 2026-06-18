import { expect, test } from '@playwright/test'

import { installWorkflowVideoMockApi, loginAs, loginAsAdmin, videoMockState } from './workflow-video-mock'

const captureEditorAccounts = [
  { taskId: 'task-capture-a', email: 'demo.video.copy.a@example.com' },
  { taskId: 'task-capture-b', email: 'demo.video.copy.b@example.com' },
  { taskId: 'task-capture-c', email: 'demo.video.copy.c@example.com' },
] as const

const copyLeadEmail = 'demo.video.copy.lead@example.com'

test.describe.configure({ mode: 'serial', timeout: 90_000 })

test.describe('workflow video v1 (W10)', () => {
  test.beforeEach(async ({ page }) => {
    videoMockState.captureSubmitted.clear()
    videoMockState.finalized = false
    videoMockState.forked = false
    videoMockState.sessionActive = false
    videoMockState.rejectedTopicIds.clear()
    videoMockState.childInstanceIds = []
    videoMockState.childRootTaskIds = []
    await installWorkflowVideoMockApi(page)
    await loginAsAdmin(page)
  })

  test('W10-1 graph tab instantiate, three captures, aggregate, batch dashboard', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await expect(page.getByTestId('task-templates-graph-tab')).toBeVisible()

    await page.getByRole('row', { name: '选题会（批次）' }).getByTestId('graph-template-instantiate').click()
    await expect(page.getByTestId('template-instantiate-dialog')).toBeVisible()
    await page.locator('.workflow-dialog__hint').isVisible()
    await page.getByTestId('template-instantiate-submit').click()

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 15_000 })

    for (const { taskId, email } of captureEditorAccounts) {
      await loginAs(page, email)
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await expect(page.getByTestId('template-capture-panel')).toBeVisible()
      await page.getByTestId('template-capture-title').fill('E2E 选题')
      const captureResponse = page.waitForResponse(
        (res) => res.url().includes('/submit-capture') && res.ok(),
      )
      await page.getByTestId('template-capture-submit').click()
      await captureResponse
    }

    await loginAs(page, copyLeadEmail)
    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.goto(`/task-center?filter=tracking&selected=task-n2-aggregate`)
    await expect(page.getByTestId('template-aggregate-panel')).toBeVisible()
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(3)
    const finalizeResponse = page.waitForResponse(
      (res) => res.url().includes('/finalize-topics') && res.ok(),
    )
    await page.getByTestId('template-aggregate-submit').click()
    await finalizeResponse

    await loginAsAdmin(page)
    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 15_000 })
    expect(videoMockState.childRootTaskIds.length).toBe(3)
    await page.goto(`/task-center?filter=stats&selected=${videoMockState.rootTaskId}`)
    await expect(page.getByTestId('task-center-stats-view')).toBeVisible()

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.childRootTaskIds[0]}`)
    await expect(page.getByText('制作交付')).toBeVisible()
  })

  test('W10-2 two approved topics fork two child runs on dashboard', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await page.getByRole('row', { name: '选题会（批次）' }).getByTestId('graph-template-instantiate').click()
    await page.getByTestId('template-instantiate-submit').click()

    for (const { taskId, email } of captureEditorAccounts.slice(0, 2)) {
      await loginAs(page, email)
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await expect(page.getByTestId('template-capture-panel')).toBeVisible()
      const captureResponse = page.waitForResponse(
        (res) => res.url().includes('/submit-capture') && res.ok(),
      )
      await page.getByTestId('template-capture-title').fill('E2E 选题')
      await page.getByTestId('template-capture-submit').click()
      await captureResponse
    }

    await loginAs(page, copyLeadEmail)
    await page.goto('/task-center?filter=tracking&selected=task-n2-aggregate')
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(2)
    const finalizeResponse = page.waitForResponse(
      (res) => res.url().includes('/finalize-topics') && res.ok(),
    )
    await page.getByTestId('template-aggregate-submit').click()
    await finalizeResponse

    await loginAsAdmin(page)
    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 15_000 })
    expect(videoMockState.childRootTaskIds.length).toBe(2)
  })
})
