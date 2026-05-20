<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createMessageReceipt, getMessageCenterSnapshot } from '@/api/messages'
import AttachmentActions from '@/components/attachments/AttachmentActions.vue'
import type {
  Message,
  MessageCenterSnapshot,
  MessageStateFilter,
  NotificationChannel,
  NotificationDelivery,
  NotificationDeliveryStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const router = useRouter()
const loading = ref(false)
const receiptSubmitting = ref(false)
const snapshot = ref<MessageCenterSnapshot | null>(null)
const selectedMessageId = ref('')
const sourceFilter = ref('all')
const stateFilter = ref<MessageStateFilter>('all')
const channelFilter = ref<NotificationChannel | 'all'>('all')
const deliveryStatusFilter = ref<NotificationDeliveryStatus | 'all'>('all')
const createdRange = ref<[Date, Date] | null>(null)

const channelOptions: Array<{ label: string; value: NotificationChannel | 'all' }> = [
  { label: '全部渠道', value: 'all' },
  { label: '邮件', value: 'email' },
  { label: '浏览器推送', value: 'web_push' },
  { label: '站内消息', value: 'websocket' },
]

const deliveryStatusOptions: Array<{ label: string; value: NotificationDeliveryStatus | 'all' }> = [
  { label: '全部投递态', value: 'all' },
  { label: '等待投递', value: 'pending' },
  { label: '投递成功', value: 'sent' },
  { label: '投递失败', value: 'failed' },
  { label: '重试中', value: 'retrying' },
]

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
      channel: channelFilter.value === 'all' ? undefined : channelFilter.value,
      deliveryStatus: deliveryStatusFilter.value === 'all' ? undefined : deliveryStatusFilter.value,
      createdFrom: createdRange.value?.[0]?.toISOString(),
      createdTo: createdRange.value?.[1]?.toISOString(),
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

function handleChannelFilterChange(value: NotificationChannel | 'all'): void {
  channelFilter.value = value
  void loadData()
}

function handleDeliveryStatusChange(value: NotificationDeliveryStatus | 'all'): void {
  deliveryStatusFilter.value = value
  void loadData()
}

function handleCreatedRangeChange(value: [Date, Date] | null): void {
  createdRange.value = value
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

function formatChannelLabel(channel: NotificationChannel): string {
  if (channel === 'email') {
    return '邮件'
  }
  if (channel === 'web_push') {
    return '浏览器推送'
  }
  return '站内消息'
}

function resolveDeliveryStateLabel(deliveryState: NotificationDeliveryStatus | null): string {
  if (deliveryState === 'sent') {
    return '投递成功'
  }
  if (deliveryState === 'failed') {
    return '投递失败'
  }
  if (deliveryState === 'retrying') {
    return '重试中'
  }
  if (deliveryState === 'pending') {
    return '等待投递'
  }
  return '暂无投递记录'
}

function resolveDeliveryStateTagType(
  deliveryState: NotificationDeliveryStatus | null,
): 'success' | 'warning' | 'danger' | 'info' {
  if (deliveryState === 'sent') {
    return 'success'
  }
  if (deliveryState === 'failed') {
    return 'danger'
  }
  if (deliveryState === 'retrying') {
    return 'warning'
  }
  return 'info'
}

function resolveDeliveryTagType(delivery: NotificationDelivery): 'success' | 'warning' | 'danger' | 'info' {
  return resolveDeliveryStateTagType(delivery.status)
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
  <div class="page filum-page">
    <el-row :gutter="16">
      <el-col v-for="item in summaryCards" :key="item.label" :xs="12" :lg="6">
        <el-card shadow="never" class="filum-metric-card">
          <div class="page__metric-label">{{ item.label }}</div>
          <div class="page__metric-value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never" class="filum-panel-card" v-loading="loading">
          <template #header>
            <div class="page__header filum-page-header">
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
                <el-select
                  :model-value="channelFilter"
                  size="small"
                  style="width: 150px"
                  @change="handleChannelFilterChange"
                >
                  <el-option
                    v-for="item in channelOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <el-select
                  :model-value="deliveryStatusFilter"
                  size="small"
                  style="width: 150px"
                  @change="handleDeliveryStatusChange"
                >
                  <el-option
                    v-for="item in deliveryStatusOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <el-date-picker
                  :model-value="createdRange"
                  type="datetimerange"
                  range-separator="至"
                  start-placeholder="开始时间"
                  end-placeholder="结束时间"
                  value-format=""
                  @change="handleCreatedRangeChange"
                />
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
            <el-table-column label="投递" width="120">
              <template #default="{ row }: { row: Message }">
                <el-tag :type="resolveDeliveryStateTagType(row.delivery_state)" effect="plain">
                  {{ resolveDeliveryStateLabel(row.delivery_state) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="附件" width="80">
              <template #default="{ row }: { row: Message }">
                {{ row.attachments.length }}
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
        <el-card shadow="never" class="filum-panel-card">
          <template #header>
            <div class="page__header filum-page-header">
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
              <el-descriptions-item label="投递状态">
                <el-tag :type="resolveDeliveryStateTagType(selectedMessage.delivery_state)" effect="plain">
                  {{ resolveDeliveryStateLabel(selectedMessage.delivery_state) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="正文">{{ selectedMessage.body_text }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatDateTime(selectedMessage.created_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>消息附件</el-divider>
            <el-empty v-if="selectedMessage.attachments.length === 0" description="暂无消息附件" />
            <div v-else class="page__attachment-list">
              <div
                v-for="attachment in selectedMessage.attachments"
                :key="attachment.id"
                class="page__attachment-item"
              >
                <div>
                  <strong>{{ attachment.original_filename }}</strong>
                  <p>{{ attachment.mime_type }} · {{ attachment.size_bytes }} bytes</p>
                </div>
                <AttachmentActions :attachment="attachment" />
              </div>
            </div>

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
            <div v-else class="page__delivery-list">
              <div
                v-for="delivery in selectedMessage.deliveries"
                :key="delivery.id"
                class="page__delivery-item"
              >
                <div class="page__delivery-head">
                  <el-tag effect="plain">{{ formatChannelLabel(delivery.channel) }}</el-tag>
                  <el-tag :type="resolveDeliveryTagType(delivery)" effect="plain">
                    {{ resolveDeliveryStateLabel(delivery.status) }}
                  </el-tag>
                </div>
                <p>
                  尝试 {{ delivery.attempt_count }} 次
                  · 最近尝试 {{ formatDateTime(delivery.attempted_at) }}
                  · 送达 {{ formatDateTime(delivery.delivered_at) }}
                </p>
                <p v-if="delivery.error_message" class="page__delivery-error">{{ delivery.error_message }}</p>
              </div>
            </div>
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
  color: var(--filum-text-secondary);
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.page__metric-value {
  font-size: 28px;
  font-weight: 600;
  margin-top: 8px;
  color: var(--filum-text);
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__attachment-list,
.page__delivery-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page__attachment-item,
.page__delivery-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.page__attachment-item p,
.page__delivery-item p {
  margin: 4px 0 0;
  color: var(--filum-text-secondary);
}

.page__delivery-item {
  align-items: flex-start;
  flex-direction: column;
}

.page__delivery-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page__delivery-error {
  color: var(--el-color-danger);
}
</style>
