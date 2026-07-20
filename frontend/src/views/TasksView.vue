<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import { listDepartments } from '@/api/departments'
import {
  createTask,
  getTaskStatsSummary,
  getTaskWorkload,
  listTaskBoard,
  listTaskGantt,
  listTasks,
} from '@/api/tasks'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type {
  Department,
  Task,
  TaskBoardColumn,
  TaskGanttEntry,
  TaskPriority,
  TaskCenterUserOption,
  TaskStatus,
  TaskStatsSummary,
  TaskWorkloadRow,
  User,
} from '@/types/api'
import TaskDetailShell from '@/components/task-detail/TaskDetailShell.vue'
import {
  resolveTaskUserFacingStateForTask,
  TASK_USER_FACING_STATE_LABELS,
  userFacingStateTagType,
} from '@/domain/task-detail/user-state'
import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  showCreateTaskComposer?: boolean
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  hideStats?: boolean
  hideViewToggle?: boolean
  externalViewMode?: 'list' | 'board' | 'gantt'
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待办',
  doing: '进行中',
  review: '评审中',
  blocked: '已阻塞',
  done: '已完成',
}

const STATUS_TAG_TYPES: Record<TaskStatus, '' | 'info' | 'warning' | 'success'> = {
  todo: 'info',
  doing: 'warning',
  review: '',
  blocked: 'warning',
  done: 'success',
}

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: '低',
  medium: '中',
  high: '高',
  urgent: '紧急',
}

const PRIORITY_TAG_TYPES: Record<TaskPriority, '' | 'info' | 'warning' | 'danger'> = {
  low: 'info',
  medium: '',
  high: 'warning',
  urgent: 'danger',
}

const authStore = useAuthStore()
const props = withDefaults(defineProps<Props>(), {
  showCreateTaskComposer: true,
  delegateUserOptions: () => [],
  hideStats: false,
  hideViewToggle: false,
})
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const tasks = ref<Task[]>([])
const taskBoard = ref<TaskBoardColumn[]>([])
const taskGantt = ref<TaskGanttEntry[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const selectedTaskId = ref('')
const viewMode = ref<'list' | 'board' | 'gantt'>('list')
const form = reactive({
  title: '',
  description: '',
  assignee_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
})

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const userEmailMap = computed(() => new Map(users.value.map((user) => [user.id, user.email])))
const assigneeOptions = computed(() => {
  if (authStore.isManagementRole) {
    return users.value.filter((user) => user.status === 'active')
  }

  return authStore.user ? [authStore.user] : []
})
const completionRateText = computed(() => formatRate(statsSummary.value?.completion_rate ?? 0))
const overdueRateText = computed(() => formatRate(statsSummary.value?.overdue_rate ?? 0))

function normalizeTagType(value: '' | 'info' | 'warning' | 'success' | 'danger'): 'info' | 'warning' | 'success' | 'danger' | undefined {
  return value || undefined
}

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resolveUserLabel(userId: string, preferredLabel?: string | null): string {
  if (preferredLabel) {
    return preferredLabel
  }
  return userEmailMap.value.get(userId) ?? `用户 ${userId.slice(0, 8)}`
}

function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}

function resolveTaskListRunLabel(task: Task): string {
  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  return resolveTaskRunLabel(task.title, metadata)
}

function formatRate(value: number): string {
  return `${Math.round(value * 100)}%`
}

function resetTaskForm(): void {
  form.title = ''
  form.description = ''
  form.assignee_id = authStore.user?.id ?? ''
  form.department_id = ''
  form.priority = 'medium'
  form.due_date = null
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [taskList, boardColumns, ganttEntries, departmentList, summary, workload] = await Promise.all([
      listTasks(),
      listTaskBoard(),
      listTaskGantt(),
      listDepartments(),
      getTaskStatsSummary(),
      getTaskWorkload(),
    ])

    tasks.value = taskList
    taskBoard.value = boardColumns
    taskGantt.value = ganttEntries
    departments.value = departmentList
    statsSummary.value = summary
    workloadRows.value = workload

    if (authStore.isManagementRole) {
      users.value = await listUsers()
    } else if (authStore.user) {
      users.value = [authStore.user]
    }

    const preferredTaskId = props.initialSelectedTaskId?.trim()
    if (preferredTaskId && taskList.some((task) => task.id === preferredTaskId)) {
      selectedTaskId.value = preferredTaskId
    } else if (!taskList.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = taskList[0]?.id ?? ''
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreateTask(): Promise<void> {
  if (!form.assignee_id) {
    ElMessage.warning('请选择执行人')
    return
  }

  submitting.value = true

  try {
    await createTask({
      title: form.title.trim(),
      description: form.description || null,
      assignee_id: form.assignee_id,
      department_id: form.department_id || null,
      priority: form.priority,
      due_date: form.due_date ? form.due_date.toISOString() : null,
    })

    ElMessage.success('任务已创建')
    dialogVisible.value = false
    resetTaskForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

function handleTaskClick(task: Task): void {
  selectedTaskId.value = task.id
}

function handleShellSelectTask(taskId: string): void {
  selectedTaskId.value = taskId
}

async function handleDetailActionDone(): Promise<void> {
  await loadData()
}

onMounted(() => {
  resetTaskForm()
  void loadData()
})

watch(
  () => props.externalViewMode,
  (nextViewMode) => {
    if (nextViewMode) {
      viewMode.value = nextViewMode
    }
  },
  { immediate: true },
)

watch(
  () => props.initialSelectedTaskId,
  (nextTaskId) => {
    if (!nextTaskId) {
      return
    }
    if (tasks.value.some((task) => task.id === nextTaskId)) {
      selectedTaskId.value = nextTaskId
    }
  },
)

watch(
  () => tasks.value,
  (taskList) => {
    const preferred = props.initialSelectedTaskId?.trim()
    if (!preferred || !taskList.some((task) => task.id === preferred)) {
      return
    }
    if (selectedTaskId.value === preferred) {
      return
    }
    selectedTaskId.value = preferred
  },
)
</script>

<template>
<div class="page" data-testid="tasks-view">
    <el-row v-if="!props.hideStats" :gutter="16" class="page__summary">
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="任务总数" :value="statsSummary?.total_tasks ?? 0" />
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="已完成" :value="statsSummary?.completed_tasks ?? 0" />
          <div class="page__stat-text">完成率 {{ completionRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="逾期任务" :value="statsSummary?.overdue_tasks ?? 0" />
          <div class="page__stat-text">逾期率 {{ overdueRateText }}</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :lg="6">
        <el-card shadow="never">
          <el-statistic title="待办中" :value="statsSummary?.tasks_by_status?.todo ?? 0" />
          <div class="page__stat-text">
            评审中 {{ statsSummary?.tasks_by_status?.review ?? 0 }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :xs="24" :xl="12">
        <el-card shadow="never" v-loading="loading" data-testid="tasks-workspace-panel">
          <template #header>
            <div class="page__header">
              <el-space>
                <span>任务中心</span>
                <el-button-group v-if="!props.hideViewToggle">
                  <el-button
                    size="small"
                    :type="viewMode === 'list' ? 'primary' : undefined"
                    data-testid="task-view-list"
                    @click="viewMode = 'list'"
                  >
                    列表
                  </el-button>
                  <el-button
                    size="small"
                    :type="viewMode === 'board' ? 'primary' : undefined"
                    data-testid="task-view-board"
                    @click="viewMode = 'board'"
                  >
                    看板
                  </el-button>
                  <el-button
                    size="small"
                    :type="viewMode === 'gantt' ? 'primary' : undefined"
                    data-testid="task-view-gantt"
                    @click="viewMode = 'gantt'"
                  >
                    甘特
                  </el-button>
                </el-button-group>
              </el-space>
              <el-button v-if="props.showCreateTaskComposer" type="primary" @click="dialogVisible = true">
                新建任务
              </el-button>
            </div>
          </template>

          <template v-if="viewMode === 'list'">
            <el-table :data="tasks" stripe highlight-current-row data-testid="tasks-list-table" @row-click="handleTaskClick">
              <el-table-column prop="title" label="任务标题" min-width="180" />
              <el-table-column label="Run" min-width="140">
                <template #default="{ row }: { row: Task }">
                  {{ resolveTaskRunLabel(row.title, (row.extra_metadata as Record<string, unknown>) ?? {}) }}
                </template>
              </el-table-column>
              <el-table-column label="用户态" width="120">
                <template #default="{ row }: { row: Task }">
                  <el-tag :type="normalizeTagType(userFacingStateTagType(resolveTaskUserFacingStateForTask(row, authStore.user?.id)))" effect="plain">
                    {{ TASK_USER_FACING_STATE_LABELS[resolveTaskUserFacingStateForTask(row, authStore.user?.id)] }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="执行人" min-width="160">
                <template #default="{ row }: { row: Task }">
                  {{ resolveUserLabel(row.assignee_id, row.assignee_label) }}
                </template>
              </el-table-column>
              <el-table-column label="所属部门" min-width="160">
                <template #default="{ row }: { row: Task }">
                  {{ resolveDepartmentName(row.department_id) }}
                </template>
              </el-table-column>
              <el-table-column label="优先级" width="120">
                <template #default="{ row }: { row: Task }">
                  <el-tag :type="normalizeTagType(PRIORITY_TAG_TYPES[row.priority])" effect="plain">
                    {{ resolvePriorityLabel(row.priority) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="120">
                <template #default="{ row }: { row: Task }">
                  <el-tag :type="normalizeTagType(STATUS_TAG_TYPES[row.status])" effect="plain">
                    {{ resolveStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="截止时间" min-width="180">
                <template #default="{ row }: { row: Task }">
                  {{ formatDateTime(row.due_date) }}
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-else-if="viewMode === 'board'">
            <div class="page__board">
              <el-card
                v-for="column in taskBoard"
                :key="column.status"
                shadow="never"
                class="page__board-column"
              >
                <template #header>
                  <div class="page__board-header">
                    <span>{{ resolveStatusLabel(column.status) }}</span>
                    <el-tag effect="plain">{{ column.tasks.length }}</el-tag>
                  </div>
                </template>

                <el-empty v-if="column.tasks.length === 0" description="暂无任务" />
                <div v-else class="page__board-cards">
                  <button
                    v-for="task in column.tasks"
                    :key="task.id"
                    type="button"
                    class="page__board-card"
                    @click="handleTaskClick(task)"
                  >
                    <strong>{{ task.title }}</strong>
                    <span>{{ resolveUserLabel(task.assignee_id, task.assignee_label) }}</span>
                    <span>{{ formatDateTime(task.due_date) }}</span>
                  </button>
                </div>
              </el-card>
            </div>
          </template>

          <template v-else>
            <el-table
              :data="taskGantt"
              stripe
              @row-click="(row: TaskGanttEntry) => handleTaskClick(row.task)"
            >
              <el-table-column label="任务标题" min-width="180">
                <template #default="{ row }: { row: TaskGanttEntry }">
                  {{ row.task.title }}
                </template>
              </el-table-column>
              <el-table-column label="执行人" min-width="180">
                <template #default="{ row }: { row: TaskGanttEntry }">
                  {{ resolveUserLabel(row.task.assignee_id, row.task.assignee_label) }}
                </template>
              </el-table-column>
              <el-table-column label="起止时间" min-width="280">
                <template #default="{ row }: { row: TaskGanttEntry }">
                  {{ formatDateTime(row.task.created_at) }} ~ {{ formatDateTime(row.task.due_date) }}
                </template>
              </el-table-column>
              <el-table-column label="依赖任务" min-width="220">
                <template #default="{ row }: { row: TaskGanttEntry }">
                  {{ row.dependency_ids.join(' / ') || '—' }}
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-card>
      </el-col>

      
      <el-col :xs="24" :xl="12">
        <TaskDetailShell
          :initial-selected-task-id="selectedTaskId || undefined"
          :delegate-user-options="props.delegateUserOptions"
          @select-task="handleShellSelectTask"
          @action-done="handleDetailActionDone"
        />
      </el-col>

    </el-row>

    <el-card shadow="never" class="page__workload">
      <template #header>
        <span>负载概览</span>
      </template>

      <el-table :data="workloadRows" stripe>
        <el-table-column prop="assignee_label" label="执行人" min-width="220" />
        <el-table-column prop="department_name" label="部门" min-width="160" />
        <el-table-column prop="total_tasks" label="总任务数" width="120" />
        <el-table-column prop="open_tasks" label="进行中/待处理" width="140" />
        <el-table-column prop="completed_tasks" label="已完成" width="100" />
        <el-table-column prop="overdue_tasks" label="逾期" width="100" />
      </el-table>
    </el-card>

    <el-dialog
      v-if="props.showCreateTaskComposer"
      v-model="dialogVisible"
      title="新建任务"
      width="560px"
      @closed="resetTaskForm"
    >
      <el-form label-position="top">
        <el-form-item label="任务标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="form.assignee_id" placeholder="请选择执行人">
            <el-option
              v-for="user in assigneeOptions"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属部门">
          <el-select v-model="form.department_id" clearable placeholder="可选">
            <el-option
              v-for="department in departments"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <FilumDateTimePicker v-model="form.due_date" class="page__date-picker" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreateTask">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page__summary {
  margin-bottom: 4px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__workload {
  min-height: 100%;
}

.page__board {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.page__board-column {
  min-height: 320px;
}

.page__board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__board-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page__board-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.page__stat-text {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
}

.page__upload {
  margin-top: 12px;
}

.page__upload-button {
  margin: 12px 0 16px;
}

.page__attachment-card {
  width: 100%;
}

.page__attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__attachment-row p,
.page__timeline-text {
  margin: 8px 0 0;
  color: #606266;
}

.page__timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__inline-tag {
  margin-left: 8px;
}

.page__comments-collapse {
  margin-top: 16px;
}

.page__comment-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.page__comment-attachment-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.page__date-picker {
  width: 100%;
}

.page__node-timeline {
  width: 100%;
}

.page__node-card {
  background: var(--el-fill-color-lighter);
}

.page__node-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.page__node-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page__node-meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.page__node-meta--terminated {
  color: var(--el-color-danger);
}
</style>
