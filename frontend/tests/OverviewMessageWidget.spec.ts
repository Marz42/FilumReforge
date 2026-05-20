import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Message } from '@/types/api'

vi.mock('@/api/messages', () => ({
  getMessageCenterSnapshot: vi.fn(),
}))

import { getMessageCenterSnapshot } from '@/api/messages'
import OverviewMessageWidget from '@/components/overview/OverviewMessageWidget.vue'
import { useAppStore } from '@/stores/app'

const mockMessage: Message = {
  id: 'message-1',
  source_type: 'task',
  source_id: 'task-1',
  recipient_user_id: 'user-1',
  recipient_email: 'admin@example.com',
  message_type: 'assignment',
  title: '新任务指派',
  body_text: '你有一条新任务',
  body_html: null,
  payload: {},
  status: 'completed',
  scheduled_at: null,
  enqueued_at: '2025-01-02T08:00:00Z',
  completed_at: '2025-01-02T08:00:00Z',
  created_at: '2025-01-02T08:00:00Z',
  delivery_state: null,
  source: {
    module_key: 'task',
    module_label: '任务',
    object_type: 'task',
    object_id: 'task-1',
    object_label: '测试任务',
    target: {
      can_navigate: true,
      route_name: 'task-center',
      route_params: {},
      route_query: { selected: 'task-1' },
    },
  },
  receipt_state: {
    is_read: false,
    is_acknowledged: false,
    read_at: null,
    acknowledged_at: null,
  },
  attachments: [],
  deliveries: [],
  receipts: [],
}

describe('OverviewMessageWidget', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(getMessageCenterSnapshot).mockResolvedValue({
      items: [mockMessage],
      total_count: 1,
      filtered_count: 1,
      unread_count: 1,
      unacknowledged_count: 1,
      source_counts: [],
      applied_source_type: null,
      applied_state: 'all',
      applied_channel: null,
      applied_delivery_status: null,
      applied_created_from: null,
      applied_created_to: null,
    })
  })

  it('loads recent messages and opens the notification drawer on click', async () => {
    const wrapper = mount(OverviewMessageWidget, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(getMessageCenterSnapshot).toHaveBeenCalledWith({
      state: 'all',
      sourceType: 'all',
    })
    expect(wrapper.text()).toContain('新任务指派')

    await wrapper.find('button.overview-widget__item').trigger('click')

    const appStore = useAppStore()
    expect(appStore.notificationDrawerOpen).toBe(true)
    expect(appStore.notificationDrawerMessageId).toBe('message-1')
  })

  it('shows empty state when there are no messages', async () => {
    vi.mocked(getMessageCenterSnapshot).mockResolvedValue({
      items: [],
      total_count: 0,
      filtered_count: 0,
      unread_count: 0,
      unacknowledged_count: 0,
      source_counts: [],
      applied_source_type: null,
      applied_state: 'all',
      applied_channel: null,
      applied_delivery_status: null,
      applied_created_from: null,
      applied_created_to: null,
    })

    const wrapper = mount(OverviewMessageWidget, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('暂无消息')
  })
})
