import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import type { Message, MessageCenterSnapshot, MessageStateFilter } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

type InboxQuery = {
  sourceType?: string
  state?: MessageStateFilter
}

export function useMessagesInbox(initialQuery: InboxQuery = {}) {
  const router = useRouter()
  const loading = ref(false)
  const snapshot = ref<MessageCenterSnapshot | null>(null)
  const selectedMessageId = ref('')
  const sourceFilter = ref(initialQuery.sourceType ?? 'all')
  const stateFilter = ref<MessageStateFilter>(initialQuery.state ?? 'all')

  let pollTimer: ReturnType<typeof setInterval> | null = null

  const messages = computed(() => snapshot.value?.items ?? [])
  const unreadCount = computed(() => snapshot.value?.unread_count ?? 0)
  const selectedMessage = computed(
    () => messages.value.find((message) => message.id === selectedMessageId.value) ?? null,
  )

  async function loadInbox(overrides: Partial<InboxQuery> = {}): Promise<void> {
    if (overrides.sourceType !== undefined) {
      sourceFilter.value = overrides.sourceType
    }
    if (overrides.state !== undefined) {
      stateFilter.value = overrides.state
    }

    loading.value = true
    try {
      snapshot.value = await getMessageCenterSnapshot({
        sourceType: sourceFilter.value === 'all' ? undefined : sourceFilter.value,
        state: stateFilter.value,
      })
      const stillSelected = messages.value.some((message) => message.id === selectedMessageId.value)
      if (!stillSelected) {
        selectedMessageId.value = messages.value[0]?.id ?? ''
      }
    } catch (error) {
      ElMessage.error(getErrorMessage(error))
    } finally {
      loading.value = false
    }
  }

  async function refreshUnreadCount(): Promise<void> {
    await loadInbox({ state: 'all', sourceType: 'all' })
  }

  function startPolling(intervalMs = 60_000): void {
    stopPolling()
    pollTimer = setInterval(() => {
      void refreshUnreadCount()
    }, intervalMs)
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function markMessageRead(message: Message): Promise<void> {
    if (message.receipt_state.is_read) {
      return
    }
    await createMessageReceipt(message.id, 'read')
    await loadInbox()
  }

  async function navigateToSource(message: Message): Promise<boolean> {
    if (!message.source.target.can_navigate || !message.source.target.route_name) {
      ElMessage.warning('当前消息暂不支持回到来源')
      return false
    }

    if (!message.receipt_state.is_read) {
      try {
        await createMessageReceipt(message.id, 'read')
      } catch {
        // 回跳优先，读回执失败不阻塞导航
      }
    }

    await router.push({
      name: message.source.target.route_name,
      query: message.source.target.route_query,
    })
    return true
  }

  onBeforeUnmount(() => {
    stopPolling()
  })

  return {
    loading,
    snapshot,
    messages,
    unreadCount,
    selectedMessageId,
    selectedMessage,
    sourceFilter,
    stateFilter,
    loadInbox,
    refreshUnreadCount,
    startPolling,
    stopPolling,
    markMessageRead,
    navigateToSource,
  }
}
