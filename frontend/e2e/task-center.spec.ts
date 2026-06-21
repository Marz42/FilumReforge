import { expect, test } from './fixtures'

test('switches to tracking and renders graph-backed task details', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=tracking&selected=task-graph-1')

  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-list-view').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel').getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('需求澄清')
  await expect(page.getByTestId('tasks-graph-panel')).toContainText('验收确认')
  await expect(page.getByTestId('task-attachment-download')).toBeVisible()
})

test('switches board view with user-facing column labels', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=inbox')
  await page.getByTestId('task-view-board').click()

  await expect(page.getByTestId('task-center-board-view')).toBeVisible()
  await expect(page.getByTestId('board-column-pending')).toContainText('待处理')
  await expect(page.getByText('整理四月周报')).toBeVisible()
})

test('switches gantt view for tasks with due dates', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=tracking')
  await page.getByTestId('task-view-gantt').click()

  await expect(page.getByTestId('task-center-gantt-view')).toBeVisible()
  await expect(page.getByText('完善工作流看板验收流')).toBeVisible()
})

test('keeps inbox and tracking filters reachable in the browser flow', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')

  await expect(page.getByText('整理四月周报')).toBeVisible()
  await page.getByTestId('task-filter-tracking').click()
  await expect(page).toHaveURL(/filter=tracking/)
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-list-view').getByText('完善工作流看板验收流')).toBeVisible()
})

test('legacy tab query redirects to filter query', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?tab=tracking&selected=task-graph-1')

  await expect(page).toHaveURL(/filter=tracking/)
  await expect(page).toHaveURL(/selected=task-graph-1/)
  await expect(page.getByTestId('task-center-tracking-panel')).toBeVisible()
})
