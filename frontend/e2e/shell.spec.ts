import { expect, test, messageCenterSnapshot } from './fixtures'
import type { MessageCenterSnapshot } from '../src/types/api'

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

test('message deep link selects the push failure and retry does not mark it read', async ({ mockApi, page }) => {
  await mockApi({ authenticated: true })
  const snapshot = structuredClone(messageCenterSnapshot) as unknown as MessageCenterSnapshot
  const target = structuredClone(snapshot.items[0]!)
  target.id = 'message-push'
  target.title = '需要重试的推送'
  target.body_text = '待核对的浏览器消息'
  target.deliveries = [{ id: 'delivery-push', message_id: target.id, channel: 'web_push', adapter_name: 'web_push',
    status: 'failed', attempt_count: 1, external_message_id: null, error_message: '推送服务暂不可用',
    attempted_at: null, delivered_at: null, created_at: target.created_at }]
  snapshot.items.push(target)
  snapshot.total_count = snapshot.filtered_count = snapshot.unread_count = 2
  let retries = 0
  await page.route('**/api/v1/messages**', async (route) => {
    if (route.request().method() === 'POST' && route.request().url().endsWith('/web-push/retry')) {
      retries += 1
      target.deliveries[0]!.status = 'retrying'
      target.deliveries[0]!.error_message = null
      await route.fulfill({ status: 202, json: target })
    } else await route.fulfill({ json: snapshot })
  })
  await page.route('**/api/v1/push-subscriptions**', (route) => route.fulfill({ json:
    route.request().url().endsWith('/config') ? { public_key: null, is_enabled: false } : [] }))
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/messages?selected=message-push')
  await expect(page.getByText('待核对的浏览器消息')).toBeVisible()
  await expect(page.getByText('推送服务暂不可用')).toBeVisible()
  await page.getByTestId('retry-web-push').click()
  await expect.poll(() => retries).toBe(1)
  await expect(page.getByTestId('retry-web-push')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '标记已读', exact: true })).toBeEnabled()
  expect(errors).toEqual([])
})
