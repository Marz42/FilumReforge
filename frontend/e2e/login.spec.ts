import { expect, loginFromPage, test } from './fixtures'

test('logs in through the browser and lands on task center', async ({ mockApi, page }) => {
  await mockApi({ authenticated: false })

  await loginFromPage(page)

  await expect(page.getByText('整理四月周报')).toBeVisible()
  await expect(page.getByTestId('task-center-create-task')).toBeVisible()
})

test('shows invite activation flow when invite token is present', async ({ mockApi, page }) => {
  await mockApi({ authenticated: false })

  await page.route('**/api/v1/auth/invitations/preview?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'user-invite-1',
        email: 'new.user@example.com',
        role: 'employee',
        expires_at: '2026-12-31T00:00:00Z',
      }),
    })
  })

  await page.goto('/login?invite=playwright-invite-token')
  await expect(page.getByTestId('login-invite-activate')).toBeVisible()
  await expect(page.getByTestId('login-form')).toHaveCount(0)
  await expect(page.getByText('欢迎加入，请设置密码')).toBeVisible()
  await expect(page.getByText('new.user@example.com')).toBeVisible()
})

test('shows bootstrap wizard when system is uninitialized', async ({ mockApi, page }) => {
  await mockApi({ authenticated: false })

  await page.route('**/api/v1/auth/bootstrap-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ bootstrap_required: true }),
    })
  })

  await page.goto('/login')
  await expect(page.getByTestId('bootstrap-wizard')).toBeVisible()
  await expect(page.getByTestId('login-form')).toHaveCount(0)
  await expect(page.getByText('系统初始化')).toBeVisible()
})

test('restores session when opening the protected route directly', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/task-center')

  await expect(page).toHaveURL(/\/task-center$/)
  await expect(page.getByTestId('task-center-view')).toBeVisible()
  await expect(page.getByText('整理四月周报')).toBeVisible()
})
