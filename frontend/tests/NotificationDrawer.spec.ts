import { ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import NotificationDrawer from '@/components/shell/NotificationDrawer.vue'

describe('NotificationDrawer', () => {
  it('exposes one-click read and delegates the batch receipt operation', async () => {
    const markAllMessagesRead = vi.fn().mockResolvedValue(2)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()

    const wrapper = mount(NotificationDrawer, {
      props: { modelValue: true },
      global: {
        plugins: [ElementPlus, router],
        provide: {
          messagesInbox: {
            loading: ref(false),
            messages: ref([]),
            unreadCount: ref(2),
            selectedMessageId: ref(''),
            loadInbox: vi.fn(),
            markMessageRead: vi.fn(),
            markAllMessagesRead,
            navigateToSource: vi.fn(),
          },
        },
        stubs: {
          ElDrawer: { template: '<div><slot /></div>' },
          teleport: true,
        },
      },
    })

    const button = wrapper.find('[data-testid="notification-mark-all-read"]')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    await flushPromises()

    expect(markAllMessagesRead).toHaveBeenCalledOnce()
  })
})
