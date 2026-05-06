import { expect, test } from './fixtures'

test('switches to tracking and renders graph-backed task details', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?tab=tracking&selected=task-graph-1')

  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-tracking-panel').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByText('工作流节点追踪')).toBeVisible()
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('需求澄清')
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('验收确认')
})

test('keeps inbox and tracking tabs reachable in the browser flow', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')

  await expect(page.getByText('整理四月周报')).toBeVisible()
  await page.getByRole('tab', { name: '任务跟踪' }).click()
  await expect(page).toHaveURL(/tab=tracking/)
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-tracking-panel').getByText('完善工作流看板验收流')).toBeVisible()
})