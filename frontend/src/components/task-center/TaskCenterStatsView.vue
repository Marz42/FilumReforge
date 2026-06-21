<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { getTaskStatsSummary, getTaskWorkload } from '@/api/tasks'
import { listDepartmentRuns, listInstanceEvents } from '@/api/workflow-graph'
import type { TaskCenterSnapshot, TaskStatsSummary, TaskWorkloadRow } from '@/types/api'
import type { DepartmentRunSummary, WorkflowRunEventItem } from '@/types/workflowVideo'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const props = defineProps<{
  snapshot: TaskCenterSnapshot | null
}>()

const authStore = useAuthStore()

const loading = ref(false)
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const runEvents = ref<WorkflowRunEventItem[]>([])
const departmentRuns = ref<DepartmentRunSummary[]>([])
const selectedDepartmentId = ref('')
const selectedInstanceId = ref('')

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_instantiated: '运行已创建',
  capture_submitted: '采集已提交',
  aggregate_confirmed: '汇总已确认',
  production_run_forked: '已 fork 制作子流',
  capture_rejected: '采集已打回',
  production_deep_reject: '制作节点打回',
  node_completed: '节点已完成',
}

const departmentOptions = computed(() => props.snapshot?.publish_department_options ?? [])

const runOptions = computed(() =>
  departmentRuns.value.map((run) => ({
    value: run.instance_id,
    label: run.run_label?.trim() || `Run ${run.instance_id.slice(0, 8)}`,
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
    const departmentId = selectedDepartmentId.value || null
    const [summary, workload] = await Promise.all([
      getTaskStatsSummary(departmentId),
      getTaskWorkload(departmentId),
    ])
    statsSummary.value = summary
    workloadRows.value = workload
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadDepartmentRuns(): Promise<void> {
  if (!selectedDepartmentId.value) {
    departmentRuns.value = []
    selectedInstanceId.value = ''
    runEvents.value = []
    return
  }

  loading.value = true
  try {
    departmentRuns.value = await listDepartmentRuns(selectedDepartmentId.value)
    if (
      selectedInstanceId.value
      && !departmentRuns.value.some((run) => run.instance_id === selectedInstanceId.value)
    ) {
      selectedInstanceId.value = departmentRuns.value[0]?.instance_id ?? ''
    } else if (!selectedInstanceId.value) {
      selectedInstanceId.value = departmentRuns.value[0]?.instance_id ?? ''
    }
    if (selectedInstanceId.value) {
      await loadEventsForInstance(selectedInstanceId.value)
    } else {
      runEvents.value = []
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    departmentRuns.value = []
    runEvents.value = []
  } finally {
    loading.value = false
  }
}

async function loadEventsForInstance(instanceId: string): Promise<void> {
  if (!instanceId) {
    runEvents.value = []
    return
  }
  selectedInstanceId.value = instanceId
  loading.value = true
  try {
    const eventsPage = await listInstanceEvents(instanceId, { limit: 100 })
    runEvents.value = eventsPage.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    runEvents.value = []
  } finally {
    loading.value = false
  }
}

function syncDepartmentDefault(): void {
  if (selectedDepartmentId.value) {
    return
  }
  selectedDepartmentId.value = departmentOptions.value[0]?.id ?? ''
}

watch(
  () => props.snapshot?.publish_department_options,
  () => {
    syncDepartmentDefault()
    void loadStats()
    void loadDepartmentRuns()
  },
  { immediate: true, deep: true },
)

watch(selectedDepartmentId, () => {
  void loadStats()
  void loadDepartmentRuns()
})

onMounted(() => {
  syncDepartmentDefault()
})
</script>

<template>
  <div v-loading="loading" class="task-center-stats-view" data-testid="task-center-stats-view">
    <el-card shadow="never" class="task-center-stats-view__panel">
      <template #header>
        <div class="task-center-stats-view__panel-header">
          <strong>统计范围</strong>
          <el-select
            v-model="selectedDepartmentId"
            placeholder="选择部门"
            style="min-width: 240px"
            data-testid="task-center-stats-department"
          >
            <el-option
              v-for="option in departmentOptions"
              :key="option.id"
              :label="option.label"
              :value="option.id"
            />
          </el-select>
        </div>
      </template>
      <p v-if="departmentOptions.length === 0" class="task-center-stats-view__hint">
        当前账号暂无可筛选的部门范围。
      </p>
    </el-card>

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
          <strong>部门 Run 一览</strong>
          <el-select
            v-model="selectedInstanceId"
            placeholder="选择 Run 查看事件"
            style="min-width: 280px"
            data-testid="task-center-stats-run-select"
            @change="(value: string) => void loadEventsForInstance(value)"
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

      <el-table
        v-if="departmentRuns.length > 0"
        :data="departmentRuns"
        stripe
        data-testid="task-center-stats-runs"
        @row-click="(row: DepartmentRunSummary) => void loadEventsForInstance(row.instance_id)"
      >
        <el-table-column prop="run_label" label="Run" min-width="180">
          <template #default="{ row }: { row: DepartmentRunSummary }">
            {{ row.run_label?.trim() || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="事件数" width="100" prop="event_count" />
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }: { row: DepartmentRunSummary }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="所选部门暂无 Run 记录" />

      <el-divider v-if="runEvents.length > 0" />

      <el-empty v-if="runEvents.length === 0" description="选择 Run 查看运行事件" />
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
      当前账号仅可查看有权限部门的统计与 Run 汇总。
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
