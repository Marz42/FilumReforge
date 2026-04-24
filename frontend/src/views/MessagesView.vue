<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import type { Message, MessageCenterSnapshot, MessageStateFilter } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const router = useRouter()
const loading = ref(false)
const receiptSubmitting = ref(false)
const snapshot = ref<MessageCenterSnapshot | null>(null)
const selectedMessageId = ref('')
const sourceFilter = ref('all')
const stateFilter = ref<MessageStateFilter>('all')

const summaryCards = computed(() => [
  {
    label: '全部消息',
    value: snapshot.value?.total_count ?? 0,
  },
  {
    label: '未读',
    value: snapshot.value?.unread_count ?? 0,
  },
  {
    label: '未确认',
    value: snapshot.value?.unacknowledged_count ?? 0,
  },
  {
    label: '当前筛选结果',
    value: snapshot.value?.filtered_count ?? 0,
  },
])

const messages = computed(() => snapshot.value?.items ?? [])
const sourceOptions = computed(() => snapshot.value?.source_counts ?? [])

const selectedMessage = computed(
  () => messages.value.find((message) => message.id === selectedMessageId.value) ?? null,
)

async function loadData(): Promise<void> {
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

function handleSourceFilterChange(value: string): void {
  sourceFilter.value = value
  void loadData()
}

function handleStateFilterChange(value: string): void {
  stateFilter.value = value as MessageStateFilter
  void loadData()
}

function resolveStateLabel(message: Message): string {
  if (message.receipt_state.is_acknowledged) {
    return '已确认'
  }
  if (message.receipt_state.is_read) {
    return '已读'
  }
  return '未读'
}

function resolveStateTagType(message: Message): 'success' | 'warning' | 'info' {
  if (message.receipt_state.is_acknowledged) {
    return 'success'
  }
  if (message.receipt_state.is_read) {
    return 'warning'
  }
  return 'info'
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

async function handleNavigateToSource(): Promise<void> {
  if (!selectedMessage.value?.source.target.can_navigate || !selectedMessage.value.source.target.route_name) {
    ElMessage.warning('当前消息暂不支持回到来源')
    return
  }
  await router.push({
    name: selectedMessage.value.source.target.route_name,
    query: selectedMessage.value.source.target.route_query,
  })
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col v-for="item in summaryCards" :key="item.label" :xs="12" :lg="6">
        <el-card shadow="never">
          <div class="page__metric-label">{{ item.label }}</div>
          <div class="page__metric-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>消息收件箱</span>
              <el-space wrap>
                <el-select
                  :model-value="stateFilter"
                  size="small"
                  style="width: 140px"
                  @change="handleStateFilterChange"
                >
                  <el-option label="全部状态" value="all" />
                  <el-option label="未读" value="unread" />
                  <el-option label="已读" value="read" />
                  <el-option label="未确认" value="unacknowledged" />
                  <el-option label="已确认" value="acknowledged" />
                </el-select>
                <el-select
                  :model-value="sourceFilter"
                  size="small"
                  style="width: 160px"
                  @change="handleSourceFilterChange"
                >
                  <el-option label="全部来源" value="all" />
                  <el-option
                    v-for="item in sourceOptions"
                    :key="item.source_type"
                    :label="`${item.label} (${item.count})`"
                    :value="item.source_type"
                  />
                </el-select>
              </el-space>
            </div>
          </template>

          <el-table :data="messages" highlight-current-row @row-click="(row: Message) => (selectedMessageId = row.id)">
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column label="来源" width="140">
              <template #default="{ row }: { row: Message }">
                <el-tag effect="plain">{{ row.source.module_label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }: { row: Message }">
                <el-tag :type="resolveStateTagType(row)" effect="plain">
                  {{ resolveStateLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
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
                <el-button
                  size="small"
                  type="primary"
                  :disabled="selectedMessage.receipt_state.is_read"
                  :loading="receiptSubmitting"
                  @click="handleReceipt('read')"
                >
                  标记已读
                </el-button>
                <el-button
                  size="small"
                  type="success"
                  :disabled="selectedMessage.receipt_state.is_acknowledged"
                  :loading="receiptSubmitting"
                  @click="handleReceipt('acknowledged')"
                >
                  确认收到
                </el-button>
                <el-button
                  size="small"
                  type="info"
                  :disabled="!selectedMessage.source.target.can_navigate"
                  @click="handleNavigateToSource"
                >
                  回到来源
                </el-button>
              </el-space>
            </div>
          </template>

          <template v-if="selectedMessage">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="标题">{{ selectedMessage.title }}</el-descriptions-item>
              <el-descriptions-item label="来源模块">{{ selectedMessage.source.module_label }}</el-descriptions-item>
              <el-descriptions-item label="来源对象">{{ selectedMessage.source.object_label || '—' }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ selectedMessage.message_type }}</el-descriptions-item>
              <el-descriptions-item label="当前状态">
                <el-tag :type="resolveStateTagType(selectedMessage)" effect="plain">
                  {{ resolveStateLabel(selectedMessage) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="正文">{{ selectedMessage.body_text }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatDateTime(selectedMessage.created_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>我的回执</el-divider>
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

            <el-divider>投递状态</el-divider>
            <el-empty v-if="selectedMessage.deliveries.length === 0" description="暂无投递记录" />
            <el-space v-else wrap>
              <el-tag
                v-for="delivery in selectedMessage.deliveries"
                :key="delivery.id"
                :type="delivery.status === 'failed' ? 'danger' : delivery.status === 'sent' ? 'success' : 'info'"
              >
                {{ delivery.channel }} · {{ delivery.status }}
              </el-tag>
            </el-space>
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

.page__metric-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.page__metric-value {
  font-size: 28px;
  font-weight: 600;
  margin-top: 8px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
