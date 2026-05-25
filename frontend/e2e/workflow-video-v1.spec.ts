import { expect, test } from '@playwright/test'

import { installWorkflowVideoMockApi, loginAsAdmin, videoMockState } from './workflow-video-mock'

test.describe.configure({ mode: 'serial', timeout: 90_000 })

test.describe('workflow video v1 (W10)', () => {
  test.beforeEach(async ({ page }) => {
    videoMockState.captureSubmitted.clear()
    videoMockState.finalized = false
    videoMockState.forked = false
    videoMockState.sessionActive = false
    videoMockState.childInstanceIds = []
    videoMockState.childRootTaskIds = []
    await installWorkflowVideoMockApi(page)
    await loginAsAdmin(page)
  })

  test('W10-1 graph tab instantiate, three captures, aggregate, batch dashboard', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await expect(page.getByTestId('task-templates-graph-tab')).toBeVisible()

    await page.getByTestId('graph-template-instantiate').click()
    await expect(page.getByTestId('template-instantiate-dialog')).toBeVisible()
    await page.locator('.workflow-dialog__hint').isVisible()
    await page.getByTestId('template-instantiate-submit').click()

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await expect(page.getByTestId('batch-run-dashboard')).toBeVisible({ timeout: 15_000 })

    for (const taskId of ['task-capture-a', 'task-capture-b', 'task-capture-c']) {
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await expect(page.getByTestId('template-capture-panel')).toBeVisible()
      await page.locator('[data-testid="template-capture-panel"] tbody input').first().fill('E2E 选题')
      const captureResponse = page.waitForResponse(
        (res) => res.url().includes('/submit-capture') && res.ok(),
      )
      await page.getByTestId('template-capture-submit').click()
      await captureResponse
    }

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

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('batch-run-dashboard')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('batch-run-event-timeline')).toBeVisible()
    await expect(page.locator('[data-testid="batch-run-dashboard"] tbody tr')).toHaveCount(3)

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.childRootTaskIds[0]}`)
    await expect(page.getByText('制作 Run')).toBeVisible()
  })

  test('W10-2 two approved topics fork two child runs on dashboard', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await page.getByTestId('graph-template-instantiate').click()
    await page.getByTestId('template-instantiate-submit').click()

    for (const taskId of ['task-capture-a', 'task-capture-b']) {
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      const captureResponse = page.waitForResponse(
        (res) => res.url().includes('/submit-capture') && res.ok(),
      )
      await page.locator('[data-testid="template-capture-panel"] tbody input').first().fill('E2E 选题')
      await page.getByTestId('template-capture-submit').click()
      await captureResponse
    }

    await page.goto('/task-center?filter=tracking&selected=task-n2-aggregate')
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(2)
    const finalizeResponse = page.waitForResponse(
      (res) => res.url().includes('/finalize-topics') && res.ok(),
    )
    await page.getByTestId('template-aggregate-submit').click()
    await finalizeResponse

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('batch-run-dashboard')).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('[data-testid="batch-run-dashboard"] tbody tr')).toHaveCount(2)
  })
})
