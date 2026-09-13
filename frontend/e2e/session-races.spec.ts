import { expect, test } from './fixtures'

test('late inbox data cannot overwrite the newer tracking filter', async ({ mockApi, page }) => {
  await mockApi()
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  let release!: () => void
  let arrived = false
  const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/v1/tasks?**', async (route) => {
    if (new URL(route.request().url()).searchParams.getAll('ids').includes('task-inbox-1')) {
      arrived = true
      await gate
    }
    await route.fallback()
  })
  await page.goto('/task-center')
  await expect.poll(() => arrived).toBe(true)
  await page.getByTestId('task-filter-tracking').click()
  const list = page.getByTestId('task-center-list-view')
  await expect(list.getByText('完善工作流看板验收流')).toBeVisible()
  release()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())))
  await expect(list.getByText('整理四月周报')).toHaveCount(0)
  await expect(list.getByText('完善工作流看板验收流')).toBeVisible()
  await expect(page.locator('.el-message--error')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('logout and next-account login reject a late old-account response without reload', async ({ mockApi, page }) => {
  await mockApi()
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  let release!: () => void
  let arrived = false
  let nextAccount = false
  const gate = new Promise<void>((resolve) => { release = resolve })
  const user = { id: 'user-b', email: 'b@example.com', role: 'employee', status: 'active',
    last_login_at: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
  const task = { id: 'account-b-task', title: '新账号独立任务', description: null,
    creator_id: user.id, assignee_id: user.id, department_id: null, status: 'todo', priority: 'medium',
    due_date: null, started_at: null, completed_at: null, parent_task_id: null, source_type: 'manual',
    extra_metadata: {}, created_at: user.created_at, updated_at: user.updated_at }
  let finishLogout!: () => void
  const logoutGate = new Promise<void>((resolve) => { finishLogout = resolve })
  await page.route('**/api/v1/auth/logout', async (route) => {
    await logoutGate
    await route.fulfill({ status: 200, json: {} })
  })
  await page.route('**/api/v1/auth/login', (route) => {
    nextAccount = true
    return route.fulfill({ json: { access_token: 'account-b-token', token_type: 'bearer', user } })
  })
  await page.route('**/api/v1/task-center', (route) => nextAccount
    ? route.fulfill({ json: { permissions: { can_publish_task: false, can_manage_templates: false },
      task_inbox: [{ task_id: task.id, title: task.title, status: 'todo', priority: 'medium' }],
      task_tracking: [], task_history: [], publish_user_options: [], publish_department_options: [], template_summaries: [] } })
    : route.fallback())
  await page.route('**/api/v1/tasks?**', async (route) => {
    const ids = new URL(route.request().url()).searchParams.getAll('ids')
    if (ids.includes(task.id)) { await route.fulfill({ json: [task] }); return }
    if (ids.includes('task-inbox-1')) { arrived = true; await gate }
    await route.fallback()
  })
  await page.goto('/task-center')
  await expect.poll(() => arrived).toBe(true)
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login/)
  await page.locator('[data-testid="login-email"] input').fill(user.email)
  await page.locator('[data-testid="login-password"] input').fill('StrongPassword123!')
  await page.getByTestId('login-submit').click()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())))
  expect(nextAccount).toBe(false)
  finishLogout()
  await expect(page.getByText(user.email, { exact: true })).toBeVisible()
  await page.getByRole('menuitem', { name: '任务中心' }).click()
  const list = page.getByTestId('task-center-list-view')
  await expect(list.getByText(task.title)).toBeVisible()
  release()
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())))
  await expect(list.getByText('整理四月周报')).toHaveCount(0)
  await expect(list.getByText(task.title)).toBeVisible()
  await expect(page.locator('.el-message--error')).toHaveCount(0)
  expect(errors).toEqual([])
})
