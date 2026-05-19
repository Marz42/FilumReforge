import { expect, test } from './fixtures'

test('switches to tracking and renders graph-backed task details', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=tracking&selected=task-graph-1')

  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-tracking-panel').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByText('工作流节点追踪')).toBeVisible()
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('需求澄清')
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('验收确认')
  await expect(page.getByTestId('task-attachment-download')).toBeVisible()
})

test('keeps inbox and tracking filters reachable in the browser flow', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')

  await expect(page.getByText('整理四月周报')).toBeVisible()
  await page.getByTestId('task-filter-tracking').click()
  await expect(page).toHaveURL(/filter=tracking/)
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-tracking-panel').getByText('完善工作流看板验收流')).toBeVisible()
})

test('legacy tab query redirects to filter query', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?tab=tracking&selected=task-graph-1')

  await expect(page).toHaveURL(/filter=tracking/)
  await expect(page).toHaveURL(/selected=task-graph-1/)
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
})
