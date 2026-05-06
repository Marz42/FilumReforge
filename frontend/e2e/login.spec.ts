import { expect, loginFromPage, test } from './fixtures'

test('logs in through the browser and lands on task center', async ({ mockApi, page }) => {
  await mockApi({ authenticated: false })

  await loginFromPage(page)

  await expect(page.getByText('整理四月周报')).toBeVisible()
  await expect(page.getByTestId('task-center-create-task')).toBeVisible()
})

test('restores session when opening the protected route directly', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })

  await page.goto('/task-center')

  await expect(page).toHaveURL(/\/task-center$/)
  await expect(page.getByTestId('task-center-view')).toBeVisible()
  await expect(page.getByText('整理四月周报')).toBeVisible()
})