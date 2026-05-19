<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getMessageCenterSnapshot } from '@/api/messages'
import { useAppStore } from '@/stores/app'
import type { Message } from '@/types/api'
import { formatDateTime } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'
import { ElMessage } from 'element-plus'

const appStore = useAppStore()
const loading = ref(false)
const messages = ref<Message[]>([])

async function loadMessages(): Promise<void> {
  loading.value = true
  try {
    const snapshot = await getMessageCenterSnapshot({ state: 'all', sourceType: 'all' })
    messages.value = snapshot.items.slice(0, 5)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function handleMessageClick(message: Message): void {
  appStore.openNotificationDrawer(message.id)
}

onMounted(() => {
  void loadMessages()
})
</script>

<template>
  <el-card shadow="never" class="overview-widget filum-panel-card" data-testid="overview-widget-messages">
    <template #header>
      <div class="overview-widget__header">
        <div class="overview-widget__heading">
          <span>消息预览</span>
          <small>最近 5 条通知</small>
        </div>
      </div>
    </template>

    <div v-loading="loading">
      <el-empty v-if="messages.length === 0" description="暂无消息" />

      <div v-else class="overview-widget__list">
        <button
          v-for="message in messages"
          :key="message.id"
          type="button"
          class="overview-widget__item"
          @click="handleMessageClick(message)"
        >
          <div class="overview-widget__item-meta">
            <strong>{{ message.title }}</strong>
            <span>{{ formatDateTime(message.created_at) }}</span>
          </div>
          <p class="overview-widget__item-content">{{ message.body_text }}</p>
        </button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.overview-widget__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-widget__heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-widget__heading small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.overview-widget__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-widget__item {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--filum-border-strong);
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.overview-widget__item:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.overview-widget__item-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.overview-widget__item-meta strong {
  color: var(--filum-text);
  font-size: 14px;
}

.overview-widget__item-content {
  margin: 8px 0 0;
  color: var(--filum-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
