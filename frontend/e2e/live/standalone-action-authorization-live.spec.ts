import { expect, test, type Page } from '@playwright/test'

const password = 'FilumPlaywright123!'
const creatorEmail = 'demo.platform.lead@example.com'
const assigneeEmail = 'demo.engineer.a@example.com'

async function login(page: Page, email: string): Promise<string> {
  await page.goto('/login?redirect=/task-center')
  await page.locator('[data-testid="login-email"] input').fill(email)
  await page.locator('[data-testid="login-password"] input').fill(password)
  const response = page.waitForResponse(
    (item) => /\/api\/v1\/auth\/login\b/.test(item.url()) && item.request().method() === 'POST',
  )
  await page.getByTestId('login-submit').click()
  const loginResponse = await response
  expect(loginResponse.ok(), `login failed for ${email}: ${loginResponse.status()}`).toBeTruthy()
  const payload = (await loginResponse.json()) as { access_token: string }
  await expect(page).toHaveURL(/\/task-center/)
  return payload.access_token
}

async function logout(page: Page): Promise<void> {
  await page.getByText('退出登录', { exact: true }).first().click()
  await expect(page.getByTestId('login-form')).toBeVisible()
}

test('standalone creator tracks while assignee executes and creator reviews', async ({ page }) => {
  const taskTitle = `KI009 Live ${Date.now()}`
  const creatorToken = await login(page, creatorEmail)

  await page.getByTestId('task-center-create-task').click()
  const dialog = page.getByTestId('task-center-task-dialog')
  await dialog.locator('[data-testid="task-center-task-title"] input').fill(taskTitle)
  await dialog.getByTestId('task-center-task-assignee').locator('.el-select').click()
  await page.getByRole('option', { name: /顾晨/ }).click()
  await dialog.getByTestId('task-center-task-submit').click()
  await expect(page.getByText('任务已发布')).toBeVisible()

  const centerResponse = await page.request.get('/api/v1/task-center', {
    headers: { Authorization: `Bearer ${creatorToken}` },
  })
  expect(centerResponse.ok()).toBeTruthy()
  const creatorCenter = (await centerResponse.json()) as {
    task_tracking: Array<{
      task_id: string
      title: string
      available_actions?: Array<{ action: string }>
    }>
  }
  const creatorEntry = creatorCenter.task_tracking.find((entry) => entry.title === taskTitle)
  expect(creatorEntry, 'creator tracking entry missing').toBeTruthy()
  expect(creatorEntry?.available_actions ?? []).toEqual([])
  const taskId = creatorEntry!.task_id

  await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
  await expect(page.getByTestId('tasks-detail-panel')).toContainText(taskTitle)
  await expect(page.getByRole('button', { name: '开始处理' })).toHaveCount(0)
  await logout(page)

  const assigneeToken = await login(page, assigneeEmail)
  await page.goto(`/task-center?filter=inbox&selected=${taskId}`)
  const startButton = page.getByRole('button', { name: '开始处理' })
  await expect(startButton).toBeVisible()
  await startButton.click()
  const deliverResponse = await page.request.post(`/api/v1/tasks/${taskId}/deliverable`, {
    headers: { Authorization: `Bearer ${assigneeToken}` },
    data: { summary: `KI009 deliverable ${taskTitle}`, attachment_ids: [] },
  })
  expect(
    deliverResponse.ok(),
    `deliverable failed: ${deliverResponse.status()} ${await deliverResponse.text()}`,
  ).toBeTruthy()
  await logout(page)

  await login(page, creatorEmail)
  await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
  const approveButton = page.getByRole('button', { name: '验收通过' })
  await expect(approveButton).toBeVisible()
  const reviewResponse = page.waitForResponse(
    (item) =>
      item.url().includes(`/api/v1/tasks/${taskId}/review`) && item.request().method() === 'POST',
  )
  await approveButton.click()
  const reviewed = await reviewResponse
  expect(reviewed.ok(), `review failed: ${reviewed.status()} ${await reviewed.text()}`).toBeTruthy()
  await expect(page.getByTestId('tasks-detail-panel')).toContainText('已完成')
})
