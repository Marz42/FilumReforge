import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Message, MessageCenterSnapshot } from '@/types/api'
import { clearAuthSession } from '@/api/session'

vi.mock('@/api/messages', () => ({
  createMessageReceipt: vi.fn(),
  getMessageCenterSnapshot: vi.fn(),
}))

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import { useMessagesInbox } from '@/composables/useMessagesInbox'
import { notifyMessageReceiptUpdated } from '@/composables/useMessageUpdates'

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

  it('refreshes the header count on another inbox receipt and removes the listener on disposal', async () => {
    vi.mocked(getMessageCenterSnapshot).mockResolvedValue(buildSnapshot([buildMessage('message-1')]))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    let inbox!: ReturnType<typeof useMessagesInbox>
    const wrapper = mount(defineComponent({ setup() { inbox = useMessagesInbox(); return () => h('div') } }), { global: { plugins: [router] } })
    await inbox.loadInbox()
    expect(inbox.unreadCount.value).toBe(1)
    vi.mocked(getMessageCenterSnapshot).mockResolvedValue(buildSnapshot([]))
    notifyMessageReceiptUpdated()
    await flushPromises()
    expect(inbox.unreadCount.value).toBe(0)
    wrapper.unmount()
    notifyMessageReceiptUpdated()
    expect(getMessageCenterSnapshot).toHaveBeenCalledTimes(2)
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

  it('stops polling on logout and ignores a late inbox response', async () => {
    vi.useFakeTimers()
    let finish!: (snapshot: MessageCenterSnapshot) => void
    vi.mocked(getMessageCenterSnapshot).mockReturnValue(new Promise((done) => { finish = done }))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
    let inbox!: ReturnType<typeof useMessagesInbox>
    const wrapper = mount(defineComponent({ setup() { inbox = useMessagesInbox(); return () => h('div') } }), { global: { plugins: [router] } })
    try {
      const load = inbox.loadInbox()
      inbox.startPolling(1000)
      clearAuthSession()
      await vi.advanceTimersByTimeAsync(3000)
      expect(getMessageCenterSnapshot).toHaveBeenCalledTimes(1)
      finish(buildSnapshot([buildMessage('old-account')]))
      await load
      expect(inbox.messages.value).toEqual([])
      expect(inbox.loading.value).toBe(false)
      wrapper.unmount()
      expect(vi.getTimerCount()).toBe(0)
    } finally { wrapper.unmount(); vi.useRealTimers() }
  })
})
