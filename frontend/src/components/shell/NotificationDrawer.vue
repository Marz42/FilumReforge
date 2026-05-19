<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { useMessagesInbox } from '@/composables/useMessagesInbox'
import type { Message } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'
import { isMessageUnread, resolveMessageStateLabel } from '@/utils/messagePresentation'

type MessagesInbox = ReturnType<typeof useMessagesInbox>

const props = defineProps<{
  modelValue: boolean
  initialMessageId?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const router = useRouter()
const inbox = inject<MessagesInbox>('messagesInbox')
if (!inbox) {
  throw new Error('NotificationDrawer requires messagesInbox provider')
}

const { loading, messages, selectedMessageId, loadInbox, markMessageRead, navigateToSource } = inbox

const detailMessageId = ref('')

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      const messageId = props.initialMessageId ?? ''
      detailMessageId.value = messageId
      selectedMessageId.value = messageId
      void loadInbox({ state: messageId ? 'all' : 'unread', sourceType: 'all' })
    }
  },
)

async function handleItemClick(message: Message): Promise<void> {
  if (message.source.target.can_navigate && message.source.target.route_name) {
    drawerVisible.value = false
    await navigateToSource(message)
    return
  }

  detailMessageId.value = message.id
  selectedMessageId.value = message.id
  if (isMessageUnread(message)) {
    try {
      await markMessageRead(message)
    } catch {
      // 详情展示不阻塞
    }
  }
}

function handleViewAll(): void {
  drawerVisible.value = false
  void router.push({ name: 'messages' })
}
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    title="消息通知"
    direction="rtl"
    size="480px"
    append-to-body
    data-testid="notification-drawer"
  >
    <div v-loading="loading" class="notification-drawer">
      <p class="notification-drawer__hint">默认显示未读消息；点击可跳转到任务或汇报来源。</p>

      <el-empty v-if="!loading && messages.length === 0" description="暂无未读消息" />

      <div v-else class="notification-drawer__list">
        <button
          v-for="message in messages"
          :key="message.id"
          type="button"
          class="notification-drawer__item"
          :class="{ 'notification-drawer__item--active': detailMessageId === message.id }"
          data-testid="notification-drawer-item"
          @click="handleItemClick(message)"
        >
          <div class="notification-drawer__item-head">
            <span class="notification-drawer__item-title">{{ message.title }}</span>
            <el-tag v-if="isMessageUnread(message)" size="small" type="danger" effect="plain">未读</el-tag>
          </div>
          <div class="notification-drawer__item-meta">
            <span>{{ message.source.module_label }}</span>
            <span>{{ resolveMessageStateLabel(message) }}</span>
            <span>{{ formatDateTime(message.created_at) }}</span>
          </div>
          <p v-if="detailMessageId === message.id" class="notification-drawer__item-body">
            {{ message.body_text }}
          </p>
        </button>
      </div>

      <div class="notification-drawer__footer">
        <el-button link type="primary" data-testid="notification-view-all" @click="handleViewAll">
          查看全部消息
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.notification-drawer {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 120px);
}

.notification-drawer__hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--filum-text-secondary);
  line-height: 1.6;
}

.notification-drawer__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.notification-drawer__item {
  width: 100%;
  border: 1px solid var(--filum-border);
  border-radius: 12px;
  background: var(--filum-surface);
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.notification-drawer__item:hover,
.notification-drawer__item--active {
  border-color: rgba(91, 110, 245, 0.35);
  box-shadow: var(--filum-shadow-shell);
}

.notification-drawer__item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.notification-drawer__item-title {
  font-weight: 600;
  color: var(--filum-text);
}

.notification-drawer__item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--filum-text-muted);
}

.notification-drawer__item-body {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--filum-text-secondary);
  white-space: pre-wrap;
}

.notification-drawer__footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--filum-border);
}
</style>
