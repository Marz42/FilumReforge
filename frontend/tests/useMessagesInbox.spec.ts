import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Message, MessageCenterSnapshot } from '@/types/api'

vi.mock('@/api/messages', () => ({
  createMessageReceipt: vi.fn(),
  getMessageCenterSnapshot: vi.fn(),
}))

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import { useMessagesInbox } from '@/composables/useMessagesInbox'

function buildMessage(id: string): Message {
  return {
    id,
    title: `消息 ${id}`,
    body_text: '待处理内容',
    created_at: '2026-07-29T08:00:00Z',
    receipt_state: {
      is_read: false,
      is_acknowledged: false,
      read_at: null,
      acknowledged_at: null,
    },
    source: {
      module_label: '任务中心',
      target: { route_name: null, route_query: {}, can_navigate: false },
    },
  } as Message
}

function buildSnapshot(items: Message[]): MessageCenterSnapshot {
  return {
    items,
    total_count: items.length,
    filtered_count: items.length,
    unread_count: items.length,
    unacknowledged_count: items.length,
    source_counts: [],
    applied_source_type: null,
    applied_state: 'unread',
    applied_channel: null,
    applied_delivery_status: null,
    applied_created_from: null,
    applied_created_to: null,
  }
}

describe('useMessagesInbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('marks every unread message in the loaded inbox as read', async () => {
    const unreadMessages = [buildMessage('message-1'), buildMessage('message-2')]
    vi.mocked(getMessageCenterSnapshot)
      .mockResolvedValueOnce(buildSnapshot(unreadMessages))
      .mockResolvedValueOnce(buildSnapshot([]))
    vi.mocked(createMessageReceipt).mockResolvedValue({} as never)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()

    let inbox: ReturnType<typeof useMessagesInbox> | undefined
    const Harness = defineComponent({
      setup() {
        inbox = useMessagesInbox()
        return () => h('div')
      },
    })

    const wrapper = mount(Harness, { global: { plugins: [ElementPlus, router] } })
    await inbox?.loadInbox({ state: 'unread' })
    const markedCount = await inbox?.markAllMessagesRead()
    await flushPromises()

    expect(markedCount).toBe(2)
    expect(createMessageReceipt).toHaveBeenCalledTimes(2)
    expect(createMessageReceipt).toHaveBeenCalledWith('message-1', 'read')
    expect(createMessageReceipt).toHaveBeenCalledWith('message-2', 'read')
    expect(getMessageCenterSnapshot).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })
})
