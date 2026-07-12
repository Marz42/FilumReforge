<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import {
  getTaskStatsDetails,
  getTaskStatsScopes,
  getTaskStatsSummary,
  getTaskWorkload,
  type TaskStatsQuery,
} from '@/api/tasks'
import { listDepartmentRuns, listInstanceEvents } from '@/api/workflow-graph'
import type {
  TaskCenterSnapshot,
  TaskSourceType,
  TaskStatsDetailItem,
  TaskStatsMetric,
  TaskStatsScopes,
  TaskStatsSummary,
  TaskWorkloadRow,
} from '@/types/api'
import type { DepartmentRunSummary, WorkflowRunEventItem } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

defineProps<{
  snapshot: TaskCenterSnapshot | null
}>()

const route = useRoute()
const router = useRouter()

const statsLoading = ref(false)
const runsLoading = ref(false)
const detailsLoading = ref(false)
const scopes = ref<TaskStatsScopes | null>(null)
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const runEvents = ref<WorkflowRunEventItem[]>([])
const departmentRuns = ref<DepartmentRunSummary[]>([])
const selectedDepartmentId = ref('')
const includeSubtree = ref(false)
const selectedInstanceId = ref('')
const selectedPreset = ref<'week' | 'month' | 'last_month' | 'custom'>('month')
const startDate = ref('')
const endDate = ref('')
const ready = ref(false)

const detailsVisible = ref(false)
const detailMetric = ref<TaskStatsMetric>('created')
const detailTitle = ref('统计明细')
const detailAssigneeId = ref<string | null>(null)
const detailItems = ref<TaskStatsDetailItem[]>([])
const detailNextCursor = ref<string | null>(null)
const detailHasMore = ref(false)

let statsRequestId = 0
let runsRequestId = 0

const EVENT_TYPE_LABELS: Record<string, string> = {
  run_instantiated: '运行已创建',
  capture_submitted: '采集已提交',
  aggregate_confirmed: '汇总已确认',
  production_run_forked: '已 fork 制作子流',
  capture_rejected: '采集已打回',
  production_deep_reject: '制作节点打回',
  node_completed: '节点已完成',
}

const SOURCE_TYPE_LABELS: Record<TaskSourceType, string> = {
  manual: '单步任务',
  template: '任务流',
  event: '事件触发',
  ai: 'AI 工具',
}

const isOrganizationScope = computed(() => scopes.value?.mode === 'organization')
const departmentOptions = computed(() => scopes.value?.departments ?? [])
const runOptions = computed(() =>
  departmentRuns.value.map((run) => ({
    value: run.instance_id,
    label: run.run_label?.trim() || `Run ${run.instance_id.slice(0, 8)}`,
  })),
)

const dateRange = computed<[Date, Date] | null>({
  get: (): [Date, Date] | null => {
    if (!startDate.value || !endDate.value) {
      return null
    }
    return [new Date(`${startDate.value}T00:00:00`), new Date(`${endDate.value}T00:00:00`)]
  },
  set: (value: [Date, Date] | null) => {
    if (!value?.[0] || !value[1]) {
      return
    }
    selectedPreset.value = 'custom'
    startDate.value = formatDateInput(value[0])
    endDate.value = formatDateInput(value[1])
  },
})

const summaryCards = computed(() => [
  { metric: 'created' as const, title: '新增任务', value: statsSummary.value?.created_tasks ?? 0, suffix: undefined },
  { metric: 'completed' as const, title: '完成任务', value: statsSummary.value?.period_completed_tasks ?? 0, suffix: undefined },
  { metric: 'due' as const, title: '到期任务', value: statsSummary.value?.due_tasks ?? 0, suffix: undefined },
  { metric: 'overdue' as const, title: '逾期任务', value: statsSummary.value?.period_overdue_tasks ?? 0, suffix: undefined },
  {
    metric: 'on_time' as const,
    title: '按期完成率',
    value: Math.round((statsSummary.value?.on_time_completion_rate ?? 0) * 100),
    suffix: '%',
  },
])

function formatDateInput(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function monthRange(offset = 0): [string, string] {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const end = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)
  return [formatDateInput(start), formatDateInput(end)]
}

function weekRange(): [string, string] {
  const now = new Date()
  const weekday = now.getDay() || 7
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - weekday + 1)
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6)
  return [formatDateInput(start), formatDateInput(end)]
}

function applyPreset(value: 'week' | 'month' | 'last_month' | 'custom'): void {
  selectedPreset.value = value
  if (value === 'custom') {
    return
  }
  const [start, end] = value === 'week' ? weekRange() : monthRange(value === 'last_month' ? -1 : 0)
  startDate.value = start
  endDate.value = end
}

function currentStatsQuery(): TaskStatsQuery {
  return {
    start_date: startDate.value,
    end_date: endDate.value,
    department_id: selectedDepartmentId.value || null,
    include_subtree: includeSubtree.value,
  }
}

function hydrateFromRoute(): void {
  const defaultRange = monthRange()
  const routeStart = typeof route.query.stats_start === 'string' ? route.query.stats_start : ''
  const routeEnd = typeof route.query.stats_end === 'string' ? route.query.stats_end : ''
  startDate.value = /^\d{4}-\d{2}-\d{2}$/.test(routeStart) ? routeStart : defaultRange[0]
  endDate.value = /^\d{4}-\d{2}-\d{2}$/.test(routeEnd) ? routeEnd : defaultRange[1]
  selectedPreset.value = routeStart && routeEnd ? 'custom' : 'month'

  const routeDepartment = typeof route.query.stats_department === 'string' ? route.query.stats_department : ''
  selectedDepartmentId.value = departmentOptions.value.some((item) => item.id === routeDepartment)
    ? routeDepartment
    : departmentOptions.value[0]?.id ?? ''
  includeSubtree.value = selectedDepartmentId.value !== '' && route.query.stats_subtree === 'true'
}

function syncRouteQuery(): void {
  const query = { ...route.query }
  query.stats_start = startDate.value
  query.stats_end = endDate.value
  if (selectedDepartmentId.value) {
    query.stats_department = selectedDepartmentId.value
  } else {
    delete query.stats_department
  }
  if (selectedDepartmentId.value && includeSubtree.value) {
    query.stats_subtree = 'true'
  } else {
    delete query.stats_subtree
  }
  void router.replace({ name: 'task-center', query })
}

async function loadStats(): Promise<void> {
  const requestId = ++statsRequestId
  statsLoading.value = true
  try {
    const query = currentStatsQuery()
    const [summary, workload] = await Promise.all([
      getTaskStatsSummary(query),
      getTaskWorkload(query),
    ])
    if (requestId !== statsRequestId) {
      return
    }
    statsSummary.value = summary
    workloadRows.value = workload
  } catch (error) {
    if (requestId === statsRequestId) {
      ElMessage.error(getErrorMessage(error))
    }
  } finally {
    if (requestId === statsRequestId) {
      statsLoading.value = false
    }
  }
}

async function loadDepartmentRuns(): Promise<void> {
  const requestId = ++runsRequestId
  if (!isOrganizationScope.value || !selectedDepartmentId.value) {
    departmentRuns.value = []
    selectedInstanceId.value = ''
    runEvents.value = []
    return
  }
  runsLoading.value = true
  try {
    const runs = await listDepartmentRuns(selectedDepartmentId.value)
    if (requestId !== runsRequestId) {
      return
    }
    departmentRuns.value = runs
    selectedInstanceId.value = runs.some((run) => run.instance_id === selectedInstanceId.value)
      ? selectedInstanceId.value
      : runs[0]?.instance_id ?? ''
    await loadEventsForInstance(selectedInstanceId.value)
  } catch (error) {
    if (requestId === runsRequestId) {
      departmentRuns.value = []
      runEvents.value = []
      ElMessage.error(getErrorMessage(error))
    }
  } finally {
    if (requestId === runsRequestId) {
      runsLoading.value = false
    }
  }
}

async function loadEventsForInstance(instanceId: string): Promise<void> {
  if (!instanceId) {
    runEvents.value = []
    return
  }
  selectedInstanceId.value = instanceId
  try {
    const eventsPage = await listInstanceEvents(instanceId, { limit: 100 })
    runEvents.value = eventsPage.items
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    runEvents.value = []
  }
}

async function openDetails(
  metric: TaskStatsMetric,
  title: string,
  assigneeId: string | null = null,
): Promise<void> {
  detailMetric.value = metric
  detailTitle.value = title
  detailAssigneeId.value = assigneeId
  detailItems.value = []
  detailNextCursor.value = null
  detailHasMore.value = false
  detailsVisible.value = true
  await loadMoreDetails()
}

async function loadMoreDetails(): Promise<void> {
  detailsLoading.value = true
  try {
    const page = await getTaskStatsDetails({
      ...currentStatsQuery(),
      metric: detailMetric.value,
      assignee_id: detailAssigneeId.value,
      cursor: detailNextCursor.value,
      limit: 50,
    })
    detailItems.value = [...detailItems.value, ...page.items]
    detailNextCursor.value = page.next_cursor
    detailHasMore.value = page.has_more
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    detailsLoading.value = false
  }
}

function openTask(taskId: string): void {
  detailsVisible.value = false
  void router.push({
    name: 'task-center',
    query: { filter: 'tracking', selected: taskId },
  })
}

function resolveRunEventLabel(eventType: string): string {
  return EVENT_TYPE_LABELS[eventType] ?? eventType
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

watch(
  [startDate, endDate, selectedDepartmentId, includeSubtree],
  () => {
    if (!ready.value || !startDate.value || !endDate.value) {
      return
    }
    if (!selectedDepartmentId.value) {
      includeSubtree.value = false
    }
    syncRouteQuery()
    void loadStats()
    void loadDepartmentRuns()
  },
)

onMounted(async () => {
  try {
    scopes.value = await getTaskStatsScopes()
    hydrateFromRoute()
    ready.value = true
    syncRouteQuery()
    await Promise.all([loadStats(), loadDepartmentRuns()])
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
})
</script>

<template>
  <div class="task-center-stats-view" data-testid="task-center-stats-view">
    <el-card shadow="never" class="task-center-stats-view__panel">
      <template #header><strong>统计范围</strong></template>
      <div class="task-center-stats-view__filters">
        <el-select
          :model-value="selectedPreset"
          style="width: 130px"
          data-testid="task-center-stats-preset"
          @update:model-value="applyPreset"
        >
          <el-option label="本周" value="week" />
          <el-option label="本月" value="month" />
          <el-option label="上月" value="last_month" />
          <el-option label="自定义" value="custom" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :clearable="false"
          data-testid="task-center-stats-date-range"
        />
        <el-select
          v-if="isOrganizationScope"
          v-model="selectedDepartmentId"
          placeholder="全部授权范围"
          clearable
          style="min-width: 220px"
          data-testid="task-center-stats-department"
        >
          <el-option
            v-for="option in departmentOptions"
            :key="option.id"
            :label="option.label"
            :value="option.id"
          />
        </el-select>
        <el-checkbox
          v-if="isOrganizationScope && selectedDepartmentId"
          v-model="includeSubtree"
          data-testid="task-center-stats-include-subtree"
        >
          包含子部门
        </el-checkbox>
        <el-tag v-if="scopes?.mode === 'personal'" effect="plain">仅本人</el-tag>
      </div>
      <p class="task-center-stats-view__hint">
        周期按 Asia/Shanghai 计算；人员数据仅用于工作负载观察，不作为绩效排名。
      </p>
    </el-card>

    <div v-loading="statsLoading" class="task-center-stats-view__summary">
      <button
        v-for="card in summaryCards"
        :key="card.metric"
        type="button"
        class="task-center-stats-view__summary-button"
        :data-testid="`task-center-stats-card-${card.metric}`"
        @click="openDetails(card.metric, card.title)"
      >
        <el-card shadow="never">
          <el-statistic :title="card.title" :value="card.value" :suffix="card.suffix" />
        </el-card>
      </button>
    </div>

    <el-card v-loading="statsLoading" shadow="never" class="task-center-stats-view__panel">
      <template #header>
        <div class="task-center-stats-view__panel-header">
          <strong>人员负载</strong>
          <small>点击人员查看当前未完成任务</small>
        </div>
      </template>
      <el-table
        :data="workloadRows"
        stripe
        data-testid="task-center-stats-workload"
        @row-click="(row: TaskWorkloadRow) => openDetails('open', `${row.assignee_label} · 当前未完成`, row.assignee_id)"
      >
        <el-table-column prop="assignee_label" label="执行人" min-width="160" />
        <el-table-column prop="open_tasks" label="当前未完成" width="120" />
        <el-table-column prop="created_tasks" label="新增" width="90" />
        <el-table-column prop="period_completed_tasks" label="完成" width="90" />
        <el-table-column prop="due_tasks" label="到期" width="90" />
        <el-table-column prop="period_overdue_tasks" label="逾期" width="90" />
        <el-table-column label="按期完成率" width="120">
          <template #default="{ row }: { row: TaskWorkloadRow }">
            {{ percent(row.on_time_completion_rate) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="isOrganizationScope" v-loading="runsLoading" shadow="never" class="task-center-stats-view__panel">
      <template #header>
        <div class="task-center-stats-view__panel-header">
          <strong>部门 Run 一览</strong>
          <el-select
            v-model="selectedInstanceId"
            :disabled="!selectedDepartmentId"
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
      <el-empty v-if="!selectedDepartmentId" description="选择具体部门后查看 Run" />
      <template v-else>
        <el-table v-if="departmentRuns.length" :data="departmentRuns" stripe data-testid="task-center-stats-runs">
          <el-table-column prop="run_label" label="Run" min-width="180" />
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="event_count" label="事件数" width="100" />
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }: { row: DepartmentRunSummary }">
              {{ formatDateTime(row.created_at) }}
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="所选部门暂无 Run 记录" />
        <el-divider v-if="runEvents.length" />
        <el-timeline v-if="runEvents.length" data-testid="task-center-stats-events">
          <el-timeline-item
            v-for="event in runEvents"
            :key="event.id"
            :timestamp="formatDateTime(event.created_at)"
          >
            {{ resolveRunEventLabel(event.event_type) }}
            <span v-if="typeof event.payload.reason === 'string'">— {{ event.payload.reason }}</span>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-card>

    <el-dialog v-model="detailsVisible" :title="detailTitle" width="960px" data-testid="task-center-stats-details">
      <el-table v-loading="detailsLoading" :data="detailItems" stripe>
        <el-table-column prop="title" label="任务" min-width="220">
          <template #default="{ row }: { row: TaskStatsDetailItem }">
            <el-button link type="primary" @click="openTask(row.task_id)">{{ row.title }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_label" label="执行人" min-width="140" />
        <el-table-column prop="department_name" label="部门" min-width="140" />
        <el-table-column label="来源" width="100">
          <template #default="{ row }: { row: TaskStatsDetailItem }">
            {{ SOURCE_TYPE_LABELS[row.source_type] }}
          </template>
        </el-table-column>
        <el-table-column prop="run_label" label="Run" min-width="140" />
        <el-table-column label="截止时间" min-width="170">
          <template #default="{ row }: { row: TaskStatsDetailItem }">
            {{ formatDateTime(row.due_date) }}
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100">
          <template #default="{ row }: { row: TaskStatsDetailItem }">
            <el-tag v-if="row.is_overdue" type="danger" effect="plain">逾期</el-tag>
            <el-tag v-else-if="row.completed_at" type="success" effect="plain">已完成</el-tag>
            <el-tag v-else effect="plain">未完成</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="detailHasMore" class="task-center-stats-view__load-more">
        <el-button :loading="detailsLoading" @click="loadMoreDetails">加载更多</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.task-center-stats-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-center-stats-view__filters,
.task-center-stats-view__panel-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.task-center-stats-view__panel-header {
  justify-content: space-between;
}

.task-center-stats-view__panel-header small,
.task-center-stats-view__hint {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.task-center-stats-view__hint {
  margin: 12px 0 0;
}

.task-center-stats-view__summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.task-center-stats-view__summary-button {
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.task-center-stats-view__summary-button :deep(.el-card) {
  height: 100%;
}

.task-center-stats-view__summary-button:hover :deep(.el-card),
.task-center-stats-view__summary-button:focus-visible :deep(.el-card) {
  border-color: var(--el-color-primary);
}

.task-center-stats-view__load-more {
  display: flex;
  justify-content: center;
  padding-top: 16px;
}

@media (max-width: 1080px) {
  .task-center-stats-view__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
