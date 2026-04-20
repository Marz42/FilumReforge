import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Message } from '@/types/api'

vi.mock('@/api/messages', () => ({
  createMessageReceipt: vi.fn(),
  listMessages: vi.fn(),
}))

import { createMessageReceipt, listMessages } from '@/api/messages'
import MessagesView from '@/views/MessagesView.vue'

const mockMessage: Message = {
  id: 'message-1',
  source_type: 'workflow',
  source_id: 'instance-1',
  recipient_user_id: 'user-1',
  recipient_email: 'admin@example.com',
  message_type: 'approval_pending',
  title: '待审批：采购申请',
  body_text: '请处理采购申请审批。',
  body_html: null,
  payload: {},
  status: 'completed',
  scheduled_at: null,
  enqueued_at: '2025-01-01T00:00:00Z',
  completed_at: '2025-01-01T00:00:01Z',
  created_at: '2025-01-01T00:00:00Z',
  deliveries: [],
  receipts: [],
}

describe('Messages view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    vi.mocked(listMessages).mockResolvedValue([mockMessage])
    vi.mocked(createMessageReceipt).mockResolvedValue({
      id: 'receipt-1',
      message_id: 'message-1',
      user_id: 'user-1',
      receipt_type: 'acknowledged',
      note: null,
      created_at: '2025-01-01T00:00:30Z',
    })
  })

  it('renders message details and submits acknowledgement receipts', async () => {
    const wrapper = mount(MessagesView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          PushSubscriptionCard: true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('待审批：采购申请')
    expect(wrapper.text()).toContain('请处理采购申请审批。')

    const ackButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('确认收到'))
    expect(ackButton).toBeTruthy()
    await ackButton?.trigger('click')
    await flushPromises()

    expect(createMessageReceipt).toHaveBeenCalledWith('message-1', 'acknowledged')
  })
})
