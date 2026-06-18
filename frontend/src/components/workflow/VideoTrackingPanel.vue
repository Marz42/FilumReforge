<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { dispatchInstanceTopic, listInstanceSubmissions } from '@/api/workflow-graph'
import VideoCaptureProgressPanel from '@/components/workflow/VideoCaptureProgressPanel.vue'
import type { InstanceSubmissionsResponse } from '@/types/workflowVideo'
import type { User, WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatUserOptionLabel } from '@/utils/userDisplay'

const props = withDefaults(
  defineProps<{
    graphInstance: WorkflowGraphInstanceDetail | null
    users: User[]
    sourceNodeKey?: string
  }>(),
  {
    sourceNodeKey: 'N1_PROPOSE',
  },
)

const emit = defineEmits<{
  dispatched: []
}>()

const loading = ref(false)
const submittingTopicId = ref<string | null>(null)
const submissions = ref<InstanceSubmissionsResponse['submissions']>([])
const writerByTopicId = ref<Record<string, string>>({})

const progressPanelRef = ref<InstanceType<typeof VideoCaptureProgressPanel> | null>(null)

const writerOptions = computed(() =>
  props.users
    .filter((user) => user.status === 'active')
    .map((user) => ({
      value: user.id,
      label: formatUserOptionLabel(user),
    })),
)

const forkedTopicIds = computed(() => {
  const context = props.graphInstance?.context ?? {}
  const forked = context.forked_topics
  if (!forked || typeof forked !== 'object') {
    return new Set<string>()
  }
  return new Set(Object.keys(forked as Record<string, string>))
})

interface TrackingRow {
  key: string
  topicId: string | null
  title: string
  submitterLabel: string
  submittedAt: string | null
  nodeInstanceId: string
  pending: boolean
  dispatched: boolean
}

const trackingRows = computed((): TrackingRow[] => {
  const rows: TrackingRow[] = []
  for (const submission of submissions.value) {
    const submitterLabel =
      submission.assignee_display_name
      ?? submission.assignee_email
      ?? submission.assignee_user_id
      ?? '—'

    if (!submission.submitted_at || submission.topics.length === 0) {
      rows.push({
        key: submission.node_instance_id,
        topicId: null,
        title: '（等待采集）',
        submitterLabel,
        submittedAt: null,
        nodeInstanceId: submission.node_instance_id,
        pending: true,
        dispatched: false,
      })
      continue
    }

    for (const topic of submission.topics) {
      const topicId = topic.topic_id ?? null
      rows.push({
        key: `${submission.node_instance_id}:${topicId ?? topic.title}`,
        topicId,
        title: topic.title,
        submitterLabel,
        submittedAt: submission.submitted_at ?? null,
        nodeInstanceId: submission.node_instance_id,
        pending: false,
        dispatched: topicId ? forkedTopicIds.value.has(topicId) : false,
      })
      if (topicId && !writerByTopicId.value[topicId] && submission.assignee_user_id) {
        writerByTopicId.value[topicId] = submission.assignee_user_id
      }
    }
  }
  return rows
})

async function loadSubmissions(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    submissions.value = []
    return
  }
  loading.value = true
  try {
    const response = await listInstanceSubmissions(instanceId, props.sourceNodeKey)
    submissions.value = response.submissions
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    submissions.value = []
  } finally {
    loading.value = false
  }
}

async function handleDispatch(row: TrackingRow): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId || !row.topicId || row.pending || row.dispatched) {
    return
  }
  const writerId = writerByTopicId.value[row.topicId]
  if (!writerId) {
    ElMessage.warning('请选择脚本撰写人')
    return
  }

  submittingTopicId.value = row.topicId
  try {
    const result = await dispatchInstanceTopic(instanceId, {
      topic_id: row.topicId,
      title: row.title,
      script_writer_user_id: writerId,
      source_node_instance_id: row.nodeInstanceId,
    })
    ElMessage.success(result.message ?? '已指派并启动制作')
    emit('dispatched')
    await loadSubmissions()
    await progressPanelRef.value?.reload()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingTopicId.value = null
  }
}

onMounted(() => {
  void loadSubmissions()
})

watch(
  () => props.graphInstance?.id,
  () => {
    void loadSubmissions()
  },
)
</script>

<template>
  <div class="video-tracking" data-testid="video-tracking-panel">
    <VideoCaptureProgressPanel
      ref="progressPanelRef"
      :graph-instance="graphInstance"
      :source-node-key="sourceNodeKey"
    />

    <el-card v-loading="loading" shadow="never" class="workflow-panel">
      <template #header>
        <div class="workflow-panel__header">
          <strong>已交选题 · 增量派发</strong>
          <el-button link type="primary" @click="loadSubmissions">刷新</el-button>
        </div>
      </template>

      <el-table :data="trackingRows" border size="small" data-testid="video-tracking-table">
        <el-table-column prop="title" label="选题" min-width="160" />
        <el-table-column prop="submitterLabel" label="提交人" width="140" />
        <el-table-column label="脚本撰写人" min-width="180">
          <template #default="{ row }: { row: TrackingRow }">
            <el-select
              v-if="!row.pending && !row.dispatched && row.topicId"
              v-model="writerByTopicId[row.topicId]"
              filterable
              placeholder="选择撰写人"
              style="width: 100%"
            >
              <el-option
                v-for="option in writerOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <span v-else-if="row.dispatched" class="video-tracking__dispatched">制作中</span>
            <span v-else class="video-tracking__muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }: { row: TrackingRow }">
            <el-button
              v-if="!row.pending && !row.dispatched && row.topicId"
              type="primary"
              size="small"
              :loading="submittingTopicId === row.topicId"
              data-testid="video-tracking-dispatch"
              @click="handleDispatch(row)"
            >
              指派并启动制作
            </el-button>
            <span v-else-if="row.dispatched" class="video-tracking__dispatched">已派发</span>
            <span v-else class="video-tracking__muted">等待采集</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.video-tracking {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.video-tracking__dispatched {
  color: var(--el-color-success);
  font-size: 12px;
  font-weight: 600;
}

.video-tracking__muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
