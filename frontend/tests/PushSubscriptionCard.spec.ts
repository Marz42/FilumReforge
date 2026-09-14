import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
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
  revokePushSubscription,
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
    vi.resetAllMocks()
    vi.mocked(registerPwaServiceWorker).mockResolvedValue({ pushManager: {
      getSubscription: vi.fn().mockResolvedValue({ endpoint: activeSubscription.endpoint }),
    } } as unknown as ServiceWorkerRegistration)
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

  it('revokes only this browser while another device stays active', async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue([activeSubscription, { ...activeSubscription, id: 'other', endpoint: 'https://push.example.com/other' }])
    const unsubscribe = vi.fn().mockResolvedValue(true)
    const getSubscription = vi.fn().mockResolvedValueOnce({ endpoint: activeSubscription.endpoint, unsubscribe })
      .mockResolvedValueOnce({ endpoint: activeSubscription.endpoint, unsubscribe }).mockResolvedValue(null)
    vi.mocked(registerPwaServiceWorker).mockResolvedValue({ pushManager: { getSubscription } } as unknown as ServiceWorkerRegistration)
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.text()).toContain('其他设备 1 个已启用')
    await wrapper.get('[data-testid="push-disable"]').trigger('click')
    await flushPromises()
    expect(revokePushSubscription).toHaveBeenCalledExactlyOnceWith('subscription-1')
    expect(unsubscribe).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('does not treat another device as the current browser', async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue([{ ...activeSubscription, endpoint: 'https://push.example.com/other' }])
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="push-disable"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('本浏览器未启用')
    wrapper.unmount()
  })

  it('fails closed when configuration cannot be loaded', async () => {
    vi.mocked(getPushSubscriptionConfig).mockRejectedValue(new Error('offline'))
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.get('[data-testid="push-enable"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('reports test queue failure as an error', async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue([activeSubscription])
    vi.mocked(sendPushTestNotification).mockResolvedValue({ message_id: 'm', status: 'failed', detail: '入队失败' })
    const error = vi.spyOn(ElMessage, 'error')
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await wrapper.get('[data-testid="push-test"]').trigger('click')
    await flushPromises()
    expect(error).toHaveBeenCalledWith('入队失败')
    error.mockRestore()
    wrapper.unmount()
  })

  it('cleans up a newly created browser subscription if server registration fails', async () => {
    const unsubscribe = vi.fn().mockResolvedValue(true)
    vi.mocked(getNotificationPermission).mockReturnValue('granted')
    vi.mocked(registerPwaServiceWorker).mockResolvedValue({ pushManager: {
      getSubscription: vi.fn().mockResolvedValue(null),
      subscribe: vi.fn().mockResolvedValue({ endpoint: activeSubscription.endpoint, toJSON: () => ({ keys: { p256dh: 'key', auth: 'auth' } }), unsubscribe }),
    } } as unknown as ServiceWorkerRegistration)
    vi.mocked(createPushSubscription).mockRejectedValue(new Error('registration failed'))
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await wrapper.get('[data-testid="push-enable"]').trigger('click')
    await flushPromises()
    expect(unsubscribe).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('本浏览器未启用')
    wrapper.unmount()
  })

  it('does not report successful cleanup while the browser subscription still exists', async () => {
    vi.mocked(listPushSubscriptions).mockResolvedValue([activeSubscription])
    vi.mocked(registerPwaServiceWorker).mockResolvedValue({ pushManager: {
      getSubscription: vi.fn().mockResolvedValue({ endpoint: activeSubscription.endpoint, unsubscribe: vi.fn().mockResolvedValue(false) }),
    } } as unknown as ServiceWorkerRegistration)
    const error = vi.spyOn(ElMessage, 'error')
    const success = vi.spyOn(ElMessage, 'success')
    const wrapper = mount(PushSubscriptionCard, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await wrapper.get('[data-testid="push-disable"]').trigger('click')
    await flushPromises()
    expect(error).toHaveBeenCalledWith(expect.stringContaining('未能清理'))
    expect(success).not.toHaveBeenCalled()
    error.mockRestore(); success.mockRestore(); wrapper.unmount()
  })
})
