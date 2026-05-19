import { expect, test } from './fixtures'

test('removes messages from side navigation and exposes header bell', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/overview')
  await expect(page.getByRole('menuitem', { name: '消息中心' })).toHaveCount(0)
  await expect(page.getByTestId('header-notification-bell')).toBeVisible()
})

test('opens notification drawer and navigates to full messages page', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/overview')
  await page.getByTestId('header-notification-bell').click()
  await expect(page.getByTestId('notification-drawer')).toBeVisible()
  await expect(page.getByTestId('notification-drawer-item')).toContainText('整理四月周报')

  await page.getByTestId('notification-view-all').click()
  await expect(page).toHaveURL(/\/messages$/)
})

test('opens notification drawer from messages deep link query', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/messages?drawer=1')
  await expect(page.getByTestId('notification-drawer')).toBeVisible()
})
