<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'

import { getTask, getTaskStatsSummary, getTaskWorkload } from '@/api/tasks'
import { listInstanceEvents } from '@/api/workflow-graph'
import type { TaskCenterSnapshot, TaskStatsSummary, TaskWorkloadRow } from '@/types/api'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  snapshot: TaskCenterSnapshot | null
}>()

const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const runEvents = ref<WorkflowRunEventItem[]>([])
const selectedTaskId = ref('')

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_instantiated: '运行已创建',
  capture_submitted: '采集已提交',
  aggregate_confirmed: '汇总已确认',
  production_run_forked: '已 fork 制作子流',
  capture_rejected: '采集已打回',
  production_deep_reject: '制作节点打回',
  node_completed: '节点已完成',
}

const runOptions = computed(() =>
  (props.snapshot?.task_tracking ?? []).map((item) => ({
    value: item.task_id,
    label: item.title,
  })),
)

const completionRateText = computed(() => {
  const rate = statsSummary.value?.completion_rate ?? 0
  return `${Math.round(rate * 100)}%`
})

const overdueRateText = computed(() => {
  const rate = statsSummary.value?.overdue_rate ?? 0
  return `${Math.round(rate * 100)}%`
})

function resolveRunEventLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType
}

async function loadStats(): Promise<void> {
  loading.value = true
  try {
    const [summary, workload] = await Promise.all([getTaskStatsSummary(), getTaskWorkload()])
    statsSummary.value = summary
    workloadRows.value = workload
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadEventsForTask(taskId: string): Promise<void> {
  if (!taskId) {
    runEvents.value = []
    return
  }
  selectedTaskId.value = taskId
  loading.value = true
  try {
    const task = await getTask(taskId)
    const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
    const instanceId = typeof metadata.workflow_graph_instance_id === 'string'
      ? metadata.workflow_graph_instance_id
      : ''
    if (!instanceId) {
      runEvents.value = []
      return
    }
    const eventsPage = await listInstanceEvents(instanceId, { limit: 100 })
    runEvents.value = eventsPage.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    runEvents.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadStats()
  const preferredTaskId =
    (typeof route.query.selected === 'string' && route.query.selected)
    || runOptions.value[0]?.value
    || ''
  if (preferredTaskId) {
    void loadEventsForTask(preferredTaskId)
  }
})

watch(
  () => route.query.selected,
  (taskId) => {
    if (typeof taskId === 'string' && taskId) {
      void loadEventsForTask(taskId)
    }
  },
)
</script>

<template>
  <div v-loading="loading" class="task-center-stats-view" data-testid="task-center-stats-view">
    <el-row :gutter="16" class="task-center-stats-view__summary">
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="任务总数" :value="statsSummary?.total_tasks ?? 0" />
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="已完成" :value="statsSummary?.completed_tasks ?? 0" />
          <div class="task-center-stats-view__stat-text">完成率 {{ completionRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="逾期任务" :value="statsSummary?.overdue_tasks ?? 0" />
          <div class="task-center-stats-view__stat-text">逾期率 {{ overdueRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="待办中" :value="statsSummary?.tasks_by_status?.todo ?? 0" />
          <div class="task-center-stats-view__stat-text">
            评审中 {{ statsSummary?.tasks_by_status?.review ?? 0 }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="task-center-stats-view__panel">
      <template #header>
        <div class="task-center-stats-view__panel-header">
          <strong>运行事件</strong>
          <el-select
            v-model="selectedTaskId"
            placeholder="选择跟踪任务查看事件"
            style="min-width: 280px"
            @change="(value: string) => void loadEventsForTask(value)"
          >
            <el-option
              v-for="option in runOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </div>
      </template>

      <el-empty v-if="runEvents.length === 0" description="请选择带图实例的任务以查看运行事件" />
      <el-timeline v-else data-testid="task-center-stats-events">
        <el-timeline-item
          v-for="event in runEvents"
          :key="event.id"
          :timestamp="formatDateTime(event.created_at)"
        >
          {{ resolveRunEventLabel(event.event_type) }}
          <span v-if="typeof event.payload.reason === 'string'">
            — {{ event.payload.reason }}
          </span>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <el-card shadow="never" class="task-center-stats-view__panel">
      <template #header><strong>人员负载</strong></template>
      <el-table :data="workloadRows" stripe data-testid="task-center-stats-workload">
        <el-table-column prop="assignee_label" label="执行人" min-width="160" />
        <el-table-column prop="open_tasks" label="进行中" width="120" />
        <el-table-column prop="overdue_tasks" label="逾期" width="120" />
        <el-table-column prop="completed_tasks" label="已完成" width="120" />
      </el-table>
    </el-card>

    <p v-if="!authStore.isManagementRole" class="task-center-stats-view__hint">
      当前账号可见本部门相关汇总；管理员可见全量统计。
    </p>
  </div>
</template>

<style scoped>
.task-center-stats-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-center-stats-view__stat-text {
  margin-top: 8px;
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.task-center-stats-view__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.task-center-stats-view__hint {
  margin: 0;
  color: var(--filum-text-secondary);
  font-size: 12px;
}
</style>
