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

  await expect(page.locator('.el-message--success')).toContainText('任务已发布')
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

test('creates a scheduled graph template dispatch from dialog tab', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center')
  await page.getByTestId('task-center-create-task').click()
  await expect(page.getByTestId('task-center-task-dialog')).toBeVisible()
  await page.getByRole('tab', { name: '定时派发' }).click()
  await expect(page.getByTestId('scheduled-dispatch-form')).toBeVisible()

  await page.locator('[data-testid="scheduled-dispatch-template"]').click()
  await page
    .locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: '每周采集' })
    .first()
    .click()
  await page.getByRole('textbox', { name: /调度名称/ }).fill('E2E 每周采集')
  await page.locator('[data-testid="scheduled-dispatch-department"]').click()
  await page
    .locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: '内容部' })
    .first()
    .click()
  await page.getByTestId('task-center-schedule-submit').click()

  await expect(page.locator('.el-message--success')).toContainText('周期任务已创建')
  await expect(page.getByTestId('task-center-task-dialog')).toBeHidden()
})

test('previews task attachment in dialog', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=tracking&selected=task-graph-1')
  await expect(page.getByTestId('tasks-detail-panel')).toBeVisible()
  await expect(page.getByText('mock-spec.md')).toBeVisible()

  await page.getByTestId('task-attachment-view').click()
  await expect(page.getByTestId('attachment-preview-dialog')).toBeVisible()
  await expect(page.getByTestId('attachment-preview-rich')).toContainText('E2E 附件预览')
  await page.getByRole('button', { name: '关闭' }).click()
  await expect(page.getByTestId('attachment-preview-dialog')).toBeHidden()
})
