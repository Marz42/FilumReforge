import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MessageCenterSnapshot } from '@/types/api'

vi.mock('@/api/messages', () => ({
  createMessageReceipt: vi.fn(),
  getMessageCenterSnapshot: vi.fn(),
}))

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import MessagesView from '@/views/MessagesView.vue'

const mockSnapshot: MessageCenterSnapshot = {
  items: [
    {
      id: 'message-1',
      source_type: 'report',
      source_id: 'report-1',
      recipient_user_id: 'user-1',
      recipient_email: 'admin@example.com',
      message_type: 'report_pending',
      title: '待处理汇报：采购申请',
      body_text: '请处理采购申请审批。',
      body_html: null,
      payload: {},
      status: 'completed',
      scheduled_at: null,
      enqueued_at: '2025-01-01T00:00:00Z',
      completed_at: '2025-01-01T00:00:01Z',
      created_at: '2025-01-01T00:00:00Z',
      source: {
        module_key: 'report',
        module_label: '汇报中心',
        object_type: 'report',
        object_id: 'report-1',
        object_label: '采购申请',
        target: {
          route_name: 'reports',
          route_query: {
            selected: 'report-1',
          },
          can_navigate: true,
        },
      },
      receipt_state: {
        is_read: false,
        is_acknowledged: false,
        read_at: null,
        acknowledged_at: null,
      },
      deliveries: [],
      receipts: [],
    },
  ],
  total_count: 1,
  filtered_count: 1,
  unread_count: 1,
  unacknowledged_count: 1,
  source_counts: [
    {
      source_type: 'report',
      label: '汇报中心',
      count: 1,
    },
  ],
  applied_source_type: null,
  applied_state: 'all',
}

describe('Messages view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    vi.mocked(getMessageCenterSnapshot).mockResolvedValue(mockSnapshot)
    vi.mocked(createMessageReceipt).mockResolvedValue({
      id: 'receipt-1',
      message_id: 'message-1',
      user_id: 'user-1',
      receipt_type: 'acknowledged',
      note: null,
      created_at: '2025-01-01T00:00:30Z',
    })
  })

  it('renders message details, navigates to source, and submits acknowledgement receipts', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/messages',
          name: 'messages',
          component: MessagesView,
        },
        {
          path: '/reports',
          name: 'reports',
          component: {
            template: '<div>reports</div>',
          },
        },
      ],
    })
    await router.push({ name: 'messages' })
    await router.isReady()

    const wrapper = mount(MessagesView, {
      global: {
        plugins: [ElementPlus, router],
        stubs: {
          PushSubscriptionCard: true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('待处理汇报：采购申请')
    expect(wrapper.text()).toContain('汇报中心')
    expect(wrapper.text()).toContain('请处理采购申请审批。')

    const navigateButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('回到来源'))
    expect(navigateButton).toBeTruthy()
    await navigateButton?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('reports')
    expect(router.currentRoute.value.query.selected).toBe('report-1')

    const ackButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('确认收到'))
    expect(ackButton).toBeTruthy()
    await ackButton?.trigger('click')
    await flushPromises()

    expect(createMessageReceipt).toHaveBeenCalledWith('message-1', 'acknowledged')
  })
})
