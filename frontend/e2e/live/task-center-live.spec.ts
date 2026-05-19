import { expect, test } from '@playwright/test'

const adminEmail = 'admin@example.com'
const password = 'FilumPlaywright123!'

test('logs in with the real backend and creates a task through task center', async ({ page }) => {
  const taskTitle = `Playwright Live Task ${Date.now()}`

  await page.goto('/login?redirect=/task-center')
  await page.locator('[data-testid="login-email"] input').fill(adminEmail)
  await page.locator('[data-testid="login-password"] input').fill(password)
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/task-center(?:\?.*)?$/)
  await expect(page.getByTestId('task-center-view')).toBeVisible()

  await page.getByTestId('task-center-create-task').click()
  await expect(page.getByTestId('task-center-task-drawer')).toBeVisible()

  await page.locator('[data-testid="task-center-task-title"] input').fill(taskTitle)
  await page.locator('[data-testid="task-center-task-description"] textarea').fill('Playwright live scenario validates the real backend integration path.')

  await page.getByTestId('task-center-task-assignee').locator('.el-select').click()
  await page.getByRole('option', { name: /顾晨/ }).click()

  await page.getByTestId('task-center-task-submit').click()

  await expect(page.getByText('任务已发布')).toBeVisible()
  await page.getByTestId('task-filter-tracking').click()
  await expect(page).toHaveURL(/filter=tracking/)
  await expect(page.getByTestId('task-center-tracking-panel').getByText(taskTitle)).toBeVisible()
  await expect(page.getByTestId('tasks-detail-panel')).toContainText(taskTitle)
})