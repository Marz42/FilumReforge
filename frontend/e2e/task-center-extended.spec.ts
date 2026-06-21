import { expect, test } from './fixtures'

test('opens history tab and shows archived task', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=history')

  await expect(page.getByTestId('task-center-history-panel')).toBeVisible()
  await expect(page.getByTestId('task-center-list-view').getByText('归档旧公告')).toBeVisible()
})

test('creates a manual task from the header dialog', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')
  await page.getByTestId('task-center-create-task').click()
  await expect(page.getByTestId('task-center-task-dialog')).toBeVisible()

  await page.locator('[data-testid="task-center-task-title"] input').fill('E2E 新建任务')
  await page.locator('[data-testid="task-center-task-assignee"] .el-select').click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first().click()
  await page.getByTestId('task-center-task-submit').click()

  await expect(page.locator('.el-message')).toContainText('任务已发布')
  await expect(page.getByTestId('task-center-list-view').getByText('E2E 新建任务')).toBeVisible()
})

test('searches tasks and shows user-facing labels', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')
  await page.getByPlaceholder('搜索任务标题或说明').fill('整理四月')
  await expect(page.getByTestId('task-center-master-table')).toContainText('整理四月周报', {
    timeout: 10_000,
  })
})
