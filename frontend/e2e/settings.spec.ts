import { expect, test } from './fixtures'

test('navigates settings sections and submits password change', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  let changePasswordCalled = false

  await page.route('**/api/v1/auth/change-password', async (route) => {
    changePasswordCalled = true
    await route.fulfill({ status: 204, body: '' })
  })

  await page.goto('/settings/security')
  await expect(page.getByTestId('settings-layout')).toBeVisible()
  await expect(page.getByTestId('settings-change-password-form')).toBeVisible()

  await page.getByTestId('settings-nav-profile').click()
  await expect(page).toHaveURL(/\/settings\/profile$/)
  await expect(page.getByTestId('settings-profile-section')).toBeVisible()

  await page.getByTestId('settings-nav-notifications').click()
  await expect(page).toHaveURL(/\/settings\/notifications$/)
  await expect(page.getByTestId('settings-notifications-section')).toBeVisible()

  await page.getByTestId('settings-nav-security').click()
  await expect(page.getByTestId('settings-change-password-form')).toBeVisible()
  await page.getByTestId('settings-current-password').locator('input').fill('OldPassword123!')
  await page.getByTestId('settings-new-password').locator('input').fill('NewPassword123!')
  await page.getByTestId('settings-confirm-password').locator('input').fill('NewPassword123!')
  await page.getByTestId('settings-submit-password').click()

  await expect.poll(() => changePasswordCalled).toBe(true)
})

test('shows readable client-side password validation in settings', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/settings/security')
  await expect(page.getByTestId('settings-change-password-form')).toBeVisible()
  await page.getByTestId('settings-current-password').locator('input').fill('OldPassword123!')
  await page.getByTestId('settings-new-password').locator('input').fill('12345678')
  await page.getByTestId('settings-confirm-password').locator('input').fill('12345678')
  await page.getByTestId('settings-submit-password').click()

  await expect(page.locator('.el-message')).toContainText(/密码至少需要包含大写字母、小写字母、数字、符号中的三类/)
})
