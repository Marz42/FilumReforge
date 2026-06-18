import { expect, test } from './fixtures'

test('opens stats tab with summary cards and workload table', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center?filter=stats')

  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
  await expect(page.getByText('任务总数')).toBeVisible()
  await expect(page.getByTestId('task-center-stats-workload')).toBeVisible()
})

test('stats redirect route lands on stats filter', async ({ mockApi, page }) => {
  await mockApi()

  await page.goto('/task-center/stats')

  await expect(page).toHaveURL(/filter=stats/)
  await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
})
