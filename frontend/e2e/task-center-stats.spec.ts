import { expect, test } from './fixtures'

test('opens stats tab with summary cards and workload table', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=stats')

  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
  await expect(page.getByText('新增任务')).toBeVisible()
  await expect(page.getByTestId('task-center-stats-workload')).toBeVisible()
})

test('stats redirect route lands on stats filter', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center/stats')

  await expect(page).toHaveURL(/filter=stats/)
  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
})

test('filters stats by department and loads run events timeline', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto('/task-center?filter=stats')

  await expect(page.getByTestId('task-center-stats-department')).toBeVisible()
  await expect(page.getByTestId('task-center-stats-runs')).toContainText('E2E 批次 Run')
  await expect(page.getByTestId('task-center-stats-events')).toContainText('运行已创建')

  await page.getByTestId('task-center-stats-department').click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').filter({ hasText: '后期部' }).click()
  await expect(page.getByTestId('task-center-stats-view')).toContainText('8')

  await page.getByTestId('task-center-stats-department').click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').filter({ hasText: '内容部' }).click()
  await expect(page.getByTestId('task-center-stats-events')).toContainText('采集已提交')
})

test('board run filter narrows visible cards', async ({ mockApi, page }) => {
  await mockApi()
  await page.goto('/task-center?filter=tracking')
  await page.getByTestId('task-view-board').click()

  await expect(page.getByTestId('task-center-board-view')).toBeVisible()
  await page.getByTestId('task-center-board-run-filter').click()
  await page
    .locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: '验收 Run A' })
    .click()
  await expect(page.getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.getByText('批次 Run · 结束采集')).toBeHidden()
})
