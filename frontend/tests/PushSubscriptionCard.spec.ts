import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/push', () => ({
  createPushSubscription: vi.fn(),
  listPushSubscriptions: vi.fn(),
  revokePushSubscription: vi.fn(),
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

import { listPushSubscriptions } from '@/api/push'
import {
  getNotificationPermission,
  getWebPushPublicKey,
  isPushSupported,
} from '@/utils/pwa'
import PushSubscriptionCard from '@/components/PushSubscriptionCard.vue'

describe('Push subscription card', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listPushSubscriptions).mockResolvedValue([])
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
})
