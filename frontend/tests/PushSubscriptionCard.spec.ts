import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/push', () => ({
  createPushSubscription: vi.fn(),
  getPushSubscriptionConfig: vi.fn(),
  listPushSubscriptions: vi.fn(),
  revokePushSubscription: vi.fn(),
  sendPushTestNotification: vi.fn(),
}))

vi.mock('@/utils/pwa', () => ({
  encodeSubscriptionKey: vi.fn(),
  getNotificationPermission: vi.fn(),
  getWebPushPublicKey: vi.fn(),
  isPushSupported: vi.fn(),
  registerPwaServiceWorker: vi.fn(),
  requestNotificationPermission: vi.fn(),
  urlBase64ToUint8Array: vi.fn(),
}))

import {
  createPushSubscription,
  getPushSubscriptionConfig,
  listPushSubscriptions,
  sendPushTestNotification,
} from '@/api/push'
import {
  getNotificationPermission,
  getWebPushPublicKey,
  isPushSupported,
  registerPwaServiceWorker,
  requestNotificationPermission,
  urlBase64ToUint8Array,
} from '@/utils/pwa'
import PushSubscriptionCard from '@/components/PushSubscriptionCard.vue'

const activeSubscription = {
  id: 'subscription-1',
  user_id: 'user-1',
  endpoint: 'https://push.example.com/subscriptions/test',
  status: 'active',
  user_agent: 'Mozilla/5.0',
  last_seen_at: null,
  created_at: '2026-04-22T00:00:00Z',
  updated_at: '2026-04-22T00:00:00Z',
} as const

describe('Push subscription card', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listPushSubscriptions).mockResolvedValue([])
    vi.mocked(getPushSubscriptionConfig).mockResolvedValue({
      public_key: 'test-public-key',
      is_enabled: true,
    })
    vi.mocked(getNotificationPermission).mockReturnValue('denied')
    vi.mocked(getWebPushPublicKey).mockReturnValue('test-public-key')
    vi.mocked(isPushSupported).mockReturnValue(true)
  })

  it('shows denied permission state', async () => {
    const wrapper = mount(PushSubscriptionCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('已拒绝')
    expect(wrapper.text()).toContain('浏览器消息推送已被拒绝')
  })

  it('sends a test push when an active subscription exists', async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue([activeSubscription])
    vi.mocked(getNotificationPermission).mockReturnValue('granted')
    vi.mocked(sendPushTestNotification).mockResolvedValue({
      message_id: 'message-1',
      status: 'queued',
      detail: '测试推送已入队，请留意浏览器通知。',
    })

    const wrapper = mount(PushSubscriptionCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const button = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发送测试推送'))
    expect(button).toBeTruthy()

    await button?.trigger('click')
    await flushPromises()

    expect(sendPushTestNotification).toHaveBeenCalledTimes(1)
  })

  it('subscribes with runtime config when env public key is missing', async () => {
    const browserSubscription = {
      endpoint: 'https://push.example.com/subscriptions/runtime',
      toJSON: () => ({ keys: { p256dh: 'p256dh', auth: 'auth' } }),
      getKey: vi.fn(),
      unsubscribe: vi.fn(),
    }
    const subscribe = vi.fn().mockResolvedValue(browserSubscription)
    vi.mocked(getWebPushPublicKey).mockReturnValue('')
    vi.mocked(getNotificationPermission).mockReturnValue('default')
    vi.mocked(requestNotificationPermission).mockResolvedValue('granted')
    vi.mocked(urlBase64ToUint8Array).mockReturnValue(new Uint8Array([1, 2, 3]))
    vi.mocked(registerPwaServiceWorker).mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(null),
        subscribe,
      },
    } as unknown as ServiceWorkerRegistration)
    vi.mocked(createPushSubscription).mockResolvedValue(activeSubscription)

    const wrapper = mount(PushSubscriptionCard, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const button = wrapper
      .findAll('button')
      .find((node) => node.text().includes('启用推送'))
    expect(button).toBeTruthy()

    await button?.trigger('click')
    await flushPromises()

    expect(getPushSubscriptionConfig).toHaveBeenCalled()
    expect(urlBase64ToUint8Array).toHaveBeenCalledWith('test-public-key')
    expect(subscribe).toHaveBeenCalledTimes(1)
    expect(createPushSubscription).toHaveBeenCalledWith({
      endpoint: 'https://push.example.com/subscriptions/runtime',
      p256dh_key: 'p256dh',
      auth_key: 'auth',
      user_agent: navigator.userAgent,
    })
  })
})
