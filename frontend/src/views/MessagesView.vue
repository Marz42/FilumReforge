<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createMessageReceipt, listMessages } from '@/api/messages'
import type { Message } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const loading = ref(false)
const receiptSubmitting = ref(false)
const messages = ref<Message[]>([])
const selectedMessageId = ref('')

const selectedMessage = computed(
  () => messages.value.find((message) => message.id === selectedMessageId.value) ?? null,
)

async function loadData(): Promise<void> {
  loading.value = true
  try {
    messages.value = await listMessages()
    if (!selectedMessageId.value) {
      selectedMessageId.value = messages.value[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleReceipt(receiptType: 'read' | 'acknowledged'): Promise<void> {
  if (!selectedMessage.value) {
    ElMessage.warning('请先选择消息')
    return
  }
  receiptSubmitting.value = true
  try {
    await createMessageReceipt(selectedMessage.value.id, receiptType)
    ElMessage.success('消息回执已提交')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    receiptSubmitting.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <span>消息收件箱</span>
          </template>

          <el-table :data="messages" highlight-current-row @row-click="(row: Message) => (selectedMessageId = row.id)">
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column prop="message_type" label="类型" width="180" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column label="时间" min-width="180">
              <template #default="{ row }: { row: Message }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="12">
        <el-card shadow="never">
          <template #header>
            <div class="page__header">
              <span>消息详情</span>
              <el-space v-if="selectedMessage">
                <el-button size="small" type="primary" :loading="receiptSubmitting" @click="handleReceipt('read')">
                  标记已读
                </el-button>
                <el-button size="small" type="success" :loading="receiptSubmitting" @click="handleReceipt('acknowledged')">
                  确认收到
                </el-button>
              </el-space>
            </div>
          </template>

          <template v-if="selectedMessage">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="标题">{{ selectedMessage.title }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ selectedMessage.message_type }}</el-descriptions-item>
              <el-descriptions-item label="正文">{{ selectedMessage.body_text }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatDateTime(selectedMessage.created_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>回执</el-divider>
            <el-empty v-if="selectedMessage.receipts.length === 0" description="暂无回执" />
            <el-timeline v-else>
              <el-timeline-item
                v-for="receipt in selectedMessage.receipts"
                :key="receipt.id"
                :timestamp="formatDateTime(receipt.created_at)"
              >
                {{ receipt.receipt_type }} · {{ receipt.user_id }}
              </el-timeline-item>
            </el-timeline>
          </template>

          <el-empty v-else description="请选择左侧消息查看详情" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
