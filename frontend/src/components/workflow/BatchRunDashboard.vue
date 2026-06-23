<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listInstanceChildren, listInstanceEvents } from '@/api/workflow-graph'
import type { WorkflowGraphInstanceSummary, WorkflowRunEventItem } from '@/types/workflowVideo'
import type { WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  graphInstance: WorkflowGraphInstanceDetail | null
}>()

const emit = defineEmits<{
  'open-task': [taskId: string]
}>()

const loading = ref(false)
const children = ref<WorkflowGraphInstanceSummary[]>([])
const runEvents = ref<WorkflowRunEventItem[]>([])

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_instantiated: '运行已创建',
  capture_submitted: '采集已提交',
  aggregate_confirmed: '汇总已确认',
  production_run_forked: '已 fork 制作子流',
  capture_rejected: '采集已打回',
  production_deep_reject: '制作节点打回',
  node_completed: '节点已完成',
}

function resolveRunEventLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType
}

const forkStatus = computed(() => {
  const context = props.graphInstance?.context ?? {}
  return typeof context.fork_status === 'string' ? context.fork_status : 'pending'
})

const approvedTopics = computed(() => {
  const context = props.graphInstance?.context ?? {}
  const topics = context.approved_topics
  return Array.isArray(topics) ? topics.length : 0
})

async function loadChildren(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    children.value = []
    return
  }
  loading.value = true
  try {
    const [childRuns, eventsPage] = await Promise.all([
      listInstanceChildren(instanceId),
      listInstanceEvents(instanceId, { limit: 30 }),
    ])
    children.value = childRuns
    runEvents.value = eventsPage.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    children.value = []
    runEvents.value = []
  } finally {
    loading.value = false
  }
}

function resolveChildTitle(child: WorkflowGraphInstanceSummary): string {
  const context = child.context ?? {}
  const title = context.topic_title
  if (typeof title === 'string' && title.trim()) {
    return title
  }
  return child.run_label ?? child.id.slice(0, 8)
}

function resolveScriptAuthorLabel(child: WorkflowGraphInstanceSummary): string {
  const context = child.context ?? {}
  const authorId = context.script_author_id
  if (typeof authorId !== 'string' || !authorId) {
    return '—'
  }
  return authorId.slice(0, 8) + '…'
}

function resolveOpenTaskId(child: WorkflowGraphInstanceSummary): string | null {
  if (child.active_task_id) {
    return child.active_task_id
  }
  const rootTaskId = child.context?.root_task_id
  return typeof rootTaskId === 'string' ? rootTaskId : null
}

onMounted(() => {
  void loadChildren()
})

watch(
  () => props.graphInstance?.id,
  () => {
    void loadChildren()
  },
)
</script>

<template>
  <el-card
    v-if="graphInstance"
    v-loading="loading"
    shadow="never"
    class="workflow-panel"
    data-testid="batch-run-dashboard"
  >
    <template #header>
      <div class="workflow-panel__header">
        <strong>批次制作看板</strong>
        <el-space wrap>
          <el-tag effect="plain">已通过 {{ approvedTopics }} 题</el-tag>
          <el-tag :type="forkStatus === 'completed' ? 'success' : 'warning'" effect="plain">
            fork {{ forkStatus }}
          </el-tag>
        </el-space>
      </div>
    </template>

    <el-empty v-if="children.length === 0" description="暂无子制作流，汇总派发后将自动 fork" />

    <el-table v-else :data="children" border size="small">
      <el-table-column label="选题" min-width="160">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          {{ resolveChildTitle(row) }}
        </template>
      </el-table-column>
      <el-table-column label="脚本撰写" width="120">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          {{ resolveScriptAuthorLabel(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="current_node_key" label="当前节点" width="140" />
      <el-table-column label="进度" width="100">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          {{ row.progress_percent ?? 0 }}%
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          <el-button
            v-if="resolveOpenTaskId(row)"
            link
            type="primary"
            @click="emit('open-task', resolveOpenTaskId(row)!)"
          >
            打开当前步骤
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-divider v-if="runEvents.length > 0">运行时间线</el-divider>
    <el-timeline v-if="runEvents.length > 0" data-testid="batch-run-event-timeline">
      <el-timeline-item
        v-for="event in runEvents"
        :key="event.id"
        :timestamp="formatDateTime(event.created_at)"
      >
        {{ resolveRunEventLabel(event.event_type) }}
        <span v-if="typeof event.payload.topic_id === 'string'" class="workflow-panel__event-meta">
          选题 {{ event.payload.topic_id }}
        </span>
      </el-timeline-item>
    </el-timeline>

    <div class="workflow-panel__actions">
      <el-button @click="loadChildren">刷新子流</el-button>
    </div>
  </el-card>
</template>

<style scoped>
.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.workflow-panel__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.workflow-panel__event-meta {
  margin-left: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
