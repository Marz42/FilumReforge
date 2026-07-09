import { expect, test } from './fixtures'

import {
  TASK_BATCH_ROOT,
  TASK_HANDSHAKE_ACCEPT,
  TASK_HANDSHAKE_DELEGATE,
  TASK_HANDSHAKE_REJECT,
} from './task-center-interaction-mock'

test.describe('task center graph handshake', () => {
  test('accepts an assigned graph handshake task', async ({ mockApi, page }) => {
    await mockApi()
    await page.goto(`/task-center?filter=inbox&selected=${TASK_HANDSHAKE_ACCEPT}`)

    await expect(page.getByRole('button', { name: '接受任务' })).toBeVisible()
    await page.getByRole('button', { name: '接受任务' }).click()
    await expect(page.locator('.el-message--success')).toContainText('任务已接受')
    await expect(page.getByText('已接受待开工')).toBeVisible()
  })

  test('returns a graph handshake task to negotiation', async ({ mockApi, page }) => {
    await mockApi()
    await page.goto(`/task-center?filter=inbox&selected=${TASK_HANDSHAKE_REJECT}`)

    await page.getByRole('button', { name: '退回协商' }).click()
    await page.locator('.el-dialog').filter({ hasText: '退回协商' }).locator('textarea').fill('需调整任务范围')
    await page.getByRole('button', { name: '确认退回' }).click()

    await expect(page.locator('.el-message--success')).toContainText('任务已退回协商')
    await expect(page.getByText('已拒绝待调整')).toBeVisible()
  })

  test('delegates a graph handshake task to another user', async ({ mockApi, page }) => {
    await mockApi()
    await page.goto(`/task-center?filter=inbox&selected=${TASK_HANDSHAKE_DELEGATE}`)

    await page.getByRole('button', { name: '转办' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '转办任务' })
    await dialog.locator('.el-select').click()
    await page
      .locator('.el-select-dropdown:visible .el-select-dropdown__item')
      .filter({ hasText: 'delegate@example.com' })
      .first()
      .click()
    await dialog.locator('textarea').fill('由协作同事继续处理')
    await page.getByRole('button', { name: '确认转办' }).click()

    await expect(page.locator('.el-message--success')).toContainText('任务已转办')
  })
})

test('approves deliverable review on tracking task', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto('/task-center?filter=tracking&selected=task-graph-1')

  await expect(page.getByRole('button', { name: '验收通过' })).toBeVisible()
  await page.getByRole('button', { name: '验收通过' }).click()
  await expect(page.locator('.el-message--success')).toContainText('验收已通过')
})

test('closes batch capture from root run detail', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto(`/task-center?filter=tracking&selected=${TASK_BATCH_ROOT}`)

  const closeButton = page.getByTestId('video-batch-close-capture')
  await expect(closeButton).toBeVisible()
  await closeButton.click()
  await expect(page.locator('.el-message--success')).toContainText('采集已结束')
  await expect(closeButton).toBeHidden()
})

test('opens stats tab from detail more menu', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto(`/task-center?filter=tracking&selected=${TASK_BATCH_ROOT}`)

  await page.getByTestId('task-detail-more-menu').click()
  await page.getByTestId('task-detail-more-open-stats').click()
  await expect(page).toHaveURL(/filter=stats/)
  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
})

test('navigates to task templates from task center header', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto('/task-center')

  await page.getByTestId('task-center-open-templates').click()
  await expect(page).toHaveURL(/\/task-templates/)
})

test('stats deep-link keeps selected run context', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto(`/task-center?filter=stats&selected=${TASK_BATCH_ROOT}`)

  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
  await expect(page.getByTestId('task-center-stats-runs')).toContainText('E2E 批次 Run')
  await expect(page.getByTestId('task-center-stats-events')).toContainText('运行已创建')
  await expect(page.getByTestId('task-center-stats-events')).toContainText('采集已提交')
})
