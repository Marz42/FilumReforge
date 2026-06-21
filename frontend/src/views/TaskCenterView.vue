<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { uploadAttachment } from '@/api/attachments'
import { createTask, createTaskComment, searchTasks, type TaskSearchResult } from '@/api/tasks'
import { getTaskCenterSnapshot, fetchTaskCenterHistoryPage, fetchTaskCenterInboxPage, fetchTaskCenterTrackingPage } from '@/api/task-center'
import TaskCenterBoardView from '@/components/task-center/TaskCenterBoardView.vue'
import TaskCenterFilterCards from '@/components/task-center/TaskCenterFilterCards.vue'
import TaskCenterGanttView from '@/components/task-center/TaskCenterGanttView.vue'
import TaskCenterListView from '@/components/task-center/TaskCenterListView.vue'
import TaskCenterStatsView from '@/components/task-center/TaskCenterStatsView.vue'
import { useTaskCenterWorkspace } from '@/composables/useTaskCenterWorkspace'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import {
  type TaskCenterFilter,
  type TaskCenterViewMode,
} from '@/constants/task-center'
import { useGlobalMemoPanel } from '@/composables/useGlobalMemoPanel'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import { useAuthStore } from '@/stores/auth'
import TaskDetailShell from '@/components/task-detail/TaskDetailShell.vue'
import type {
  TaskCenterHistoryItem,
  TaskCenterInboxItem,
  TaskCenterSnapshot,
  TaskCenterTrackingItem,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'
import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'
import {
  TASK_USER_FACING_STATE_LABELS,
  userFacingStateTagType,
} from '@/domain/task-detail/user-state'

const LEGACY_TAB_TO_FILTER: Record<string, TaskCenterFilter> = {
  inbox: 'inbox',
  tracking: 'tracking',
  history: 'history',
  stats: 'stats',
  tasks: 'tracking',
  publish: 'inbox',
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待办',
  doing: '进行中',
  review: '评审中',
  done: '已完成',
}

const STATUS_TAG_TYPES: Record<TaskStatus, '' | 'info' | 'warning' | 'success'> = {
  todo: 'info',
  doing: 'warning',
  review: '',
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

const SOURCE_TYPE_LABELS: Record<TaskSourceType, string> = {
  manual: '手动发布',
  template: '模板任务',
  event: '事件触发',
  ai: 'AI 工具',
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { openPanel: openGlobalMemoPanel } = useGlobalMemoPanel()
const loading = ref(false)
const taskDialogVisible = ref(false)
const taskSearchQuery = ref('')
const taskSearchLoading = ref(false)
const taskSearchResults = ref<TaskSearchResult[]>([])
let taskSearchTimer: ReturnType<typeof setTimeout> | undefined
const publishSubmitting = ref(false)
const publishAttachmentUploading = ref(false)
const snapshot = ref<TaskCenterSnapshot | null>(null)

interface PublishDraftAttachment {
  id: string
  original_filename: string
}

const publishDraftAttachments = ref<PublishDraftAttachment[]>([])

const publishForm = reactive({
  title: '',
  description: '',
  assignee_user_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
})

const activeFilter = computed<TaskCenterFilter>(() => normalizeFilter(route.query.filter ?? route.query.tab))
const workspaceViewMode = computed<TaskCenterViewMode>(() => normalizeViewMode(route.query.view))
const selectedTaskId = computed(() => (typeof route.query.selected === 'string' ? route.query.selected : ''))
const isStatsLayout = computed(() => activeFilter.value === 'stats')
const isListLayout = computed(() => workspaceViewMode.value === 'list' && !isStatsLayout.value)
const usesWorkspace = computed(() => activeFilter.value !== 'stats')
const viewToggleDisabled = computed(() => isStatsLayout.value)

const permissions = computed(() => {
  return (
    snapshot.value?.permissions ?? {
      can_manage_templates: false,
      can_publish_task: false,
    }
  )
})
const publishDepartmentOptions = computed(() => snapshot.value?.publish_department_options ?? [])
const publishUserOptions = computed(() => snapshot.value?.publish_user_options ?? [])

const filteredPublishUserOptions = computed(() => {
  if (!publishForm.department_id) {
    return publishUserOptions.value
  }
  return publishUserOptions.value.filter(
    (user) => user.department_id === publishForm.department_id,
  )
})

const assigneeSelectPlaceholder = computed(() => {
  if (filteredPublishUserOptions.value.length === 0) {
    return '该部门暂无可选执行人'
  }
  return '请选择执行人'
})

watch(
  () => publishForm.department_id,
  () => {
    if (
      publishForm.assignee_user_id &&
      !filteredPublishUserOptions.value.some(
        (user) => user.user_id === publishForm.assignee_user_id,
      )
    ) {
      publishForm.assignee_user_id = ''
    }
  },
)

const publishFormDirty = computed(
  () => publishForm.title.trim().length > 0 || publishForm.description.trim().length > 0,
)

const filterCounts = computed(() => ({
  inbox: snapshot.value?.task_inbox.length ?? 0,
  tracking: snapshot.value?.task_tracking.length ?? 0,
  history: snapshot.value?.task_history.length ?? 0,
}))

const masterListItems = computed(() => {
  if (activeFilter.value === 'inbox') {
    return snapshot.value?.task_inbox ?? []
  }
  if (activeFilter.value === 'history') {
    return snapshot.value?.task_history ?? []
  }
  return snapshot.value?.task_tracking ?? []
})

const displayListItems = computed(() => {
  const query = taskSearchQuery.value.trim()
  if (!query) {
    return masterListItems.value
  }
  return taskSearchResults.value.map((item) => ({
    task_id: item.id,
    title: item.title,
    priority: item.priority,
    status: item.status,
    due_date: null as string | null,
    department_name: item.department_name,
    current_stage_label: '—',
    current_handler_label: null as string | null,
    relation_types: [] as string[],
    completed_at: null as string | null,
    source_type: 'manual' as TaskSourceType,
  }))
})

const isSearchMode = computed(() => taskSearchQuery.value.trim().length > 0)

const { rows: workspaceRows, loading: workspaceLoading, refresh: refreshWorkspace } = useTaskCenterWorkspace({
  filter: activeFilter,
  snapshot,
  currentUserId: computed(() => authStore.user?.id),
  enabled: computed(() => usesWorkspace.value && !isSearchMode.value),
})

const listLoadMoreLoading = ref(false)
const boardRunFilter = ref('__all__')

const activeListPagination = computed(() => {
  if (!snapshot.value || activeFilter.value === 'stats') {
    return { has_more: false, next_cursor: null as string | null }
  }
  if (activeFilter.value === 'inbox') {
    return snapshot.value.inbox_pagination ?? { has_more: false, next_cursor: null }
  }
  if (activeFilter.value === 'history') {
    return snapshot.value.history_pagination ?? { has_more: false, next_cursor: null }
  }
  return snapshot.value.tracking_pagination ?? { has_more: false, next_cursor: null }
})

const boardRunOptions = computed(() => {
  const labels = new Set<string>()
  for (const row of workspaceRows.value) {
    const label = row.runLabel?.trim()
    if (label) {
      labels.add(label)
    }
  }
  return [...labels].sort()
})

const filteredBoardRows = computed(() => {
  if (boardRunFilter.value === '__all__') {
    return workspaceRows.value
  }
  return workspaceRows.value.filter((row) => row.runLabel === boardRunFilter.value)
})

const masterListTaskIds = computed(() => new Set(displayListItems.value.map((item) => item.task_id)))

const effectiveSelectedTaskId = computed(() => {
  const id = selectedTaskId.value.trim()
  if (!id) {
    return ''
  }
  if (isSearchMode.value) {
    return taskSearchResults.value.some((item) => item.id === id) ? id : ''
  }
  return masterListTaskIds.value.has(id) ? id : ''
})

function sanitizeSelectedQuery(): void {
  const id = selectedTaskId.value.trim()
  if (!id) {
    return
  }
  const isValid = isSearchMode.value
    ? taskSearchResults.value.some((item) => item.id === id)
    : masterListTaskIds.value.has(id)
  if (isValid) {
    return
  }
  void router.replace({
    name: 'task-center',
    query: buildRouteQuery({ selected: '' }),
  })
}

const masterPanelTestId = computed(() => {
  if (activeFilter.value === 'inbox') {
    return 'task-center-inbox-panel'
  }
  if (activeFilter.value === 'history') {
    return 'task-center-history-panel'
  }
  return 'task-center-tracking-panel'
})

function normalizeFilter(rawFilter: unknown): TaskCenterFilter {
  if (typeof rawFilter !== 'string') {
    return 'inbox'
  }
  const mapped = LEGACY_TAB_TO_FILTER[rawFilter]
  if (mapped) {
    return mapped
  }
  if (rawFilter === 'inbox' || rawFilter === 'tracking' || rawFilter === 'history' || rawFilter === 'stats') {
    return rawFilter
  }
  return 'inbox'
}

function normalizeViewMode(rawView: unknown): TaskCenterViewMode {
  if (rawView === 'board' || rawView === 'gantt' || rawView === 'list') {
    return rawView
  }
  return 'list'
}

function buildRouteQuery(options: {
  filter?: TaskCenterFilter
  view?: TaskCenterViewMode
  selected?: string
}): Record<string, string> | undefined {
  const filter = options.filter ?? activeFilter.value
  const view = options.view ?? workspaceViewMode.value
  const selected = options.selected ?? selectedTaskId.value
  const query: Record<string, string> = {}

  if (filter !== 'inbox') {
    query.filter = filter
  }
  if (view !== 'list' && filter !== 'stats') {
    query.view = view
  }
  if (selected) {
    query.selected = selected
  }

  return Object.keys(query).length > 0 ? query : undefined
}

function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}

function resolveSourceTypeLabel(sourceType: TaskSourceType): string {
  return SOURCE_TYPE_LABELS[sourceType]
}

function resolveMasterRunLabel(
  row: { title: string; run_label?: string | null },
): string {
  if (row.run_label?.trim()) {
    return row.run_label.trim()
  }
  return resolveTaskRunLabel(row.title)
}

function resolveSearchUserStateLabel(row: TaskSearchResult): string {
  if (row.user_facing_state) {
    return TASK_USER_FACING_STATE_LABELS[row.user_facing_state]
  }
  return STATUS_LABELS[row.status]
}

function resolveSearchUserStateTagType(
  row: TaskSearchResult,
): '' | 'info' | 'warning' | 'success' | 'danger' {
  if (row.user_facing_state) {
    return userFacingStateTagType(row.user_facing_state)
  }
  return STATUS_TAG_TYPES[row.status]
}

function resetPublishForm(): void {
  publishForm.title = ''
  publishForm.description = ''
  publishForm.assignee_user_id = ''
  publishForm.department_id = publishDepartmentOptions.value[0]?.id ?? ''
  publishForm.priority = 'medium'
  publishForm.due_date = null
  publishDraftAttachments.value = []
}

function removePublishDraftAttachment(id: string): void {
  publishDraftAttachments.value = publishDraftAttachments.value.filter(
    (attachment) => attachment.id !== id,
  )
}

async function handlePublishDraftFileChange(uploadFile: UploadFile): Promise<void> {
  const raw = uploadFile.raw
  if (!raw) {
    return
  }
  const err = validateAttachmentFile(raw)
  if (err) {
    ElMessage.error(err)
    return
  }
  publishAttachmentUploading.value = true
  try {
    const attachment = await uploadAttachment({ file: raw })
    publishDraftAttachments.value.push({
      id: attachment.id,
      original_filename: attachment.original_filename,
    })
    ElMessage.success('附件已加入，将在建立任务时绑定')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishAttachmentUploading.value = false
  }
}

async function requestCloseTaskDialog(): Promise<boolean> {
  if (!publishFormDirty.value) {
    return true
  }
  try {
    await ElMessageBox.confirm('有未保存的内容，是否关闭？', '关闭建立任务', {
      type: 'warning',
      confirmButtonText: '关闭',
      cancelButtonText: '继续编辑',
    })
    return true
  } catch {
    return false
  }
}

async function handleTaskDialogBeforeClose(done: () => void): Promise<void> {
  if (await requestCloseTaskDialog()) {
    resetPublishForm()
    done()
  }
}

async function handleCancelTaskDialog(): Promise<void> {
  if (!(await requestCloseTaskDialog())) {
    return
  }
  taskDialogVisible.value = false
  resetPublishForm()
}

function openTaskDialog(): void {
  if (!permissions.value.can_publish_task) {
    return
  }
  resetPublishForm()
  taskDialogVisible.value = true
}

async function runTaskSearch(query: string): Promise<void> {
  const trimmed = query.trim()
  if (!trimmed) {
    taskSearchResults.value = []
    return
  }
  taskSearchLoading.value = true
  try {
    taskSearchResults.value = await searchTasks(trimmed)
    sanitizeSelectedQuery()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    taskSearchLoading.value = false
  }
}

watch(taskSearchQuery, (value) => {
  if (taskSearchTimer) {
    clearTimeout(taskSearchTimer)
  }
  taskSearchTimer = setTimeout(() => {
    void runTaskSearch(value)
  }, 300)
})

async function loadSnapshot(): Promise<void> {
  loading.value = true
  try {
    snapshot.value = await getTaskCenterSnapshot()
    if (!publishForm.department_id && publishDepartmentOptions.value.length > 0) {
      publishForm.department_id = publishDepartmentOptions.value[0]!.id
    }
    sanitizeSelectedQuery()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleDetailActionDone(): Promise<void> {
  await loadSnapshot()
  await refreshWorkspace()
}

async function handleLoadMoreListItems(): Promise<void> {
  if (!snapshot.value || !activeListPagination.value.has_more) {
    return
  }
  const cursor = activeListPagination.value.next_cursor
  if (!cursor) {
    return
  }

  listLoadMoreLoading.value = true
  try {
    if (activeFilter.value === 'inbox') {
      const page = await fetchTaskCenterInboxPage({ cursor })
      snapshot.value = {
        ...snapshot.value,
        task_inbox: [...snapshot.value.task_inbox, ...page.items],
        inbox_pagination: page.pagination,
      }
    } else if (activeFilter.value === 'history') {
      const page = await fetchTaskCenterHistoryPage({ cursor })
      snapshot.value = {
        ...snapshot.value,
        task_history: [...snapshot.value.task_history, ...page.items],
        history_pagination: page.pagination,
      }
    } else {
      const page = await fetchTaskCenterTrackingPage({ cursor })
      snapshot.value = {
        ...snapshot.value,
        task_tracking: [...snapshot.value.task_tracking, ...page.items],
        tracking_pagination: page.pagination,
      }
    }
    await refreshWorkspace()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    listLoadMoreLoading.value = false
  }
}

function handleFilterChange(value: TaskCenterFilter): void {
  void router.replace({
    name: 'task-center',
    query: buildRouteQuery({ filter: value, selected: '' }),
  })
}

function handleViewModeChange(value: TaskCenterViewMode): void {
  if (viewToggleDisabled.value) {
    return
  }
  void router.replace({
    name: 'task-center',
    query: buildRouteQuery({ view: value }),
  })
}

function handleMasterRowClick(taskId: string): void {
  void router.replace({
    name: 'task-center',
    query: buildRouteQuery({ selected: taskId }),
  })
}

function masterRowClassName({
  row,
}: {
  row: TaskCenterInboxItem | TaskCenterTrackingItem | TaskCenterHistoryItem
}): string {
  return row.task_id === selectedTaskId.value ? 'task-center-view__row--selected' : ''
}

async function handlePublishTask(): Promise<void> {
  if (!publishForm.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (!publishForm.assignee_user_id) {
    ElMessage.warning('请选择执行人')
    return
  }

  publishSubmitting.value = true
  try {
    await createTask({
      title: publishForm.title.trim(),
      description: publishForm.description.trim() || null,
      assignee_id: publishForm.assignee_user_id,
      department_id: publishForm.department_id || null,
      priority: publishForm.priority,
      due_date: publishForm.due_date ? publishForm.due_date.toISOString() : null,
      attachment_ids: publishDraftAttachments.value.map((attachment) => attachment.id),
    })
    ElMessage.success('任务已发布')
    taskDialogVisible.value = false
    resetPublishForm()
    await loadSnapshot()
    handleFilterChange('inbox')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishSubmitting.value = false
  }
}

function renderRelationTypes(item: TaskCenterTrackingItem | TaskCenterHistoryItem): string {
  return item.relation_types.join(' / ') || '—'
}

function isOverdue(item: TaskCenterTrackingItem): boolean {
  return !!(item.due_date && new Date(item.due_date) < new Date() && item.status !== 'done')
}

const nudgingTaskIds = ref<Set<string>>(new Set())

async function handleNudge(taskId: string): Promise<void> {
  nudgingTaskIds.value = new Set([...nudgingTaskIds.value, taskId])
  try {
    await createTaskComment(taskId, { content: '【催办】请及时处理此任务' })
    ElMessage.success('催办消息已发送')
  } catch {
    ElMessage.error('催办失败，请稍后重试')
  } finally {
    nudgingTaskIds.value = new Set([...nudgingTaskIds.value].filter((id) => id !== taskId))
  }
}

function renderTrackingSignals(item: TaskCenterTrackingItem): string {
  const signals: string[] = []
  if (item.is_pending_review) {
    signals.push('待验收')
  }
  if ((item.rework_count ?? 0) > 0) {
    signals.push(`返工 ${item.rework_count} 次`)
  }
  if (typeof item.review_quality_score === 'number') {
    signals.push(`质量 ${item.review_quality_score}/5`)
  }
  return signals.join(' / ') || '—'
}

function rowKey(item: TaskCenterInboxItem | TaskCenterTrackingItem | TaskCenterHistoryItem): string {
  return item.task_id
}

function migrateLegacyQuery(): void {
  const rawTab = route.query.tab
  if (typeof rawTab !== 'string') {
    return
  }

  if (rawTab === 'templates') {
    void router.replace({ name: 'task-templates' })
    return
  }

  if (rawTab === 'memos') {
    openGlobalMemoPanel()
    void router.replace({
      name: 'task-center',
      query: buildRouteQuery({ filter: 'inbox', selected: '' }),
    })
    return
  }

  const nextFilter = normalizeFilter(rawTab)
  const nextSelected = typeof route.query.selected === 'string' ? route.query.selected : ''
  void router.replace({
    name: 'task-center',
    query: buildRouteQuery({ filter: nextFilter, selected: nextSelected }),
  })
}

watch(
  () => route.fullPath,
  () => {
    migrateLegacyQuery()
  },
  { immediate: true },
)

onMounted(() => {
  resetPublishForm()
  void loadSnapshot()
})
</script>

<template>
  <div class="task-center-view filum-page" data-testid="task-center-view">
    <el-card shadow="never" class="filum-panel-card" v-loading="loading" data-testid="task-center-summary-card">
      <template #header>
        <div class="task-center-view__header filum-page-header">
          <div class="filum-page-header__copy">
            <span class="filum-page-header__eyebrow">Workflow</span>
            <strong class="filum-page-header__title">任务中心</strong>
            <p class="task-center-view__subtitle">
              通过筛选与视图切换聚焦待处理、跟踪与历史任务；个人备忘与任务模板已独立入口。
            </p>
          </div>
          <el-space wrap>
            <el-tag :type="permissions.can_publish_task ? 'success' : 'info'" effect="plain">
              {{ permissions.can_publish_task ? '可发布任务' : '仅查看任务' }}
            </el-tag>
            <el-button-group :class="{ 'task-center-view__view-toggle--disabled': viewToggleDisabled }">
              <el-button
                size="small"
                :type="workspaceViewMode === 'list' ? 'primary' : undefined"
                :disabled="viewToggleDisabled"
                data-testid="task-view-list"
                @click="handleViewModeChange('list')"
              >
                列表
              </el-button>
              <el-button
                size="small"
                :type="workspaceViewMode === 'board' ? 'primary' : undefined"
                :disabled="viewToggleDisabled"
                data-testid="task-view-board"
                @click="handleViewModeChange('board')"
              >
                看板
              </el-button>
              <el-button
                size="small"
                :type="workspaceViewMode === 'gantt' ? 'primary' : undefined"
                :disabled="viewToggleDisabled"
                data-testid="task-view-gantt"
                @click="handleViewModeChange('gantt')"
              >
                甘特
              </el-button>
            </el-button-group>
            <el-button
              v-if="permissions.can_publish_task || authStore.user?.role === 'admin'"
              data-testid="task-center-open-templates"
              @click="router.push({ name: 'task-templates' })"
            >
              任务模板
            </el-button>
            <el-button
              type="primary"
              :disabled="!permissions.can_publish_task"
              data-testid="task-center-create-task"
              @click="openTaskDialog"
            >
              建立任务
            </el-button>
          </el-space>
        </div>
      </template>

      <div class="task-center-view__search" data-testid="task-center-search">
        <el-input
          v-model="taskSearchQuery"
          clearable
          placeholder="搜索任务标题或说明"
          data-testid="task-center-search-input"
        />
      </div>

      <TaskCenterFilterCards
        :active-filter="activeFilter"
        :counts="filterCounts"
        :show-stats="true"
        @change="handleFilterChange"
      />
    </el-card>

    <TaskCenterStatsView v-if="isStatsLayout" :snapshot="snapshot" />

    <template v-else-if="isListLayout">
      <div class="task-center-view__master-detail">
        <el-card
          shadow="never"
          class="filum-panel-card task-center-view__master"
          :data-testid="masterPanelTestId"
        >
          <template #header>
            <div class="task-center-view__section-header">
              <span v-if="activeFilter === 'inbox'">待处理</span>
              <span v-else-if="activeFilter === 'tracking'">任务跟踪</span>
              <span v-else>历史任务</span>
              <small v-if="activeFilter === 'inbox'">集中查看需要你处理或确认的任务</small>
            </div>
          </template>

          <el-empty
            v-if="!isSearchMode && workspaceRows.length === 0 && !workspaceLoading"
            description="暂无任务"
          />

          <TaskCenterListView
            v-else-if="!isSearchMode"
            :filter="activeFilter"
            :rows="workspaceRows"
            :selected-task-id="effectiveSelectedTaskId"
            :loading="workspaceLoading"
            @select="handleMasterRowClick"
            @nudge="handleNudge"
          />

          <div
            v-if="!isSearchMode && activeListPagination.has_more"
            class="task-center-view__load-more"
          >
            <el-button
              :loading="listLoadMoreLoading"
              data-testid="task-center-load-more"
              @click="handleLoadMoreListItems"
            >
              加载更多
            </el-button>
          </div>

          <el-empty
            v-else-if="isSearchMode && displayListItems.length === 0"
            description="未找到匹配任务"
          />

          <el-table
            v-else-if="isSearchMode"
            v-loading="taskSearchLoading && isSearchMode"
            :data="displayListItems"
            :row-key="rowKey"
            :row-class-name="masterRowClassName"
            stripe
            highlight-current-row
            data-testid="task-center-master-table"
            @row-click="(row: TaskCenterInboxItem | TaskCenterTrackingItem | TaskCenterHistoryItem) => handleMasterRowClick(row.task_id)"
          >
            <el-table-column prop="title" label="任务标题" min-width="220" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }: { row: TaskSearchResult }">
                <el-tag :type="resolveSearchUserStateTagType(row)" effect="plain">
                  {{ resolveSearchUserStateLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="120">
              <template #default="{ row }: { row: TaskSearchResult }">
                <el-tag :type="PRIORITY_TAG_TYPES[row.priority]" effect="plain">
                  {{ resolvePriorityLabel(row.priority) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="department_name" label="部门" min-width="160" />
          </el-table>
        </el-card>

        <div class="task-center-view__detail">
          <TaskDetailShell
            :initial-selected-task-id="effectiveSelectedTaskId"
            :delegate-user-options="publishUserOptions"
            @select-task="handleMasterRowClick"
            @action-done="handleDetailActionDone"
          />
        </div>
      </div>
    </template>

    <template v-else>
      <div class="task-center-view__master-detail">
        <el-card
          shadow="never"
          class="filum-panel-card task-center-view__master"
          :data-testid="masterPanelTestId"
        >
          <template #header>
            <div class="task-center-view__section-header">
              <div>
                <span v-if="workspaceViewMode === 'board'">看板视图</span>
                <span v-else>甘特视图</span>
                <small>按用户态与 Run 展示当前筛选下的任务</small>
              </div>
              <el-select
                v-if="workspaceViewMode === 'board' && boardRunOptions.length > 0"
                v-model="boardRunFilter"
                placeholder="筛选 Run"
                style="min-width: 200px"
                data-testid="task-center-board-run-filter"
              >
                <el-option label="全部 Run" value="__all__" />
                <el-option
                  v-for="runLabel in boardRunOptions"
                  :key="runLabel"
                  :label="runLabel"
                  :value="runLabel"
                />
              </el-select>
            </div>
          </template>

          <TaskCenterBoardView
            v-if="workspaceViewMode === 'board'"
            :rows="filteredBoardRows"
            :selected-task-id="effectiveSelectedTaskId"
            :loading="workspaceLoading"
            @select="handleMasterRowClick"
          />
          <TaskCenterGanttView
            v-else
            :rows="workspaceRows"
            :selected-task-id="effectiveSelectedTaskId"
            :loading="workspaceLoading"
            @select="handleMasterRowClick"
          />
        </el-card>

        <div class="task-center-view__detail">
          <TaskDetailShell
            :initial-selected-task-id="effectiveSelectedTaskId"
            :delegate-user-options="publishUserOptions"
            @select-task="handleMasterRowClick"
            @action-done="handleDetailActionDone"
          />
        </div>
      </div>
    </template>

    <el-dialog
      v-model="taskDialogVisible"
      title="建立任务"
      width="720px"
      align-center
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      data-testid="task-center-task-dialog"
      :before-close="handleTaskDialogBeforeClose"
    >
      <el-form label-position="top" class="task-center-view__form">
        <el-form-item label="任务标题">
          <div data-testid="task-center-task-title">
            <el-input v-model="publishForm.title" placeholder="例如：完成四月客户复盘" />
          </div>
        </el-form-item>
        <el-form-item label="任务说明">
          <div data-testid="task-center-task-description" class="task-center-view__control-wrap">
            <el-input
              v-model="publishForm.description"
              type="textarea"
              :autosize="{ minRows: 4, maxRows: 10 }"
              maxlength="4000"
              show-word-limit
              placeholder="补充背景、交付要求或参考信息（可选）"
            />
          </div>
        </el-form-item>
        <el-form-item label="所属部门">
          <div data-testid="task-center-task-department" class="task-center-view__control-wrap">
            <el-select
              v-model="publishForm.department_id"
              class="task-center-view__full-select"
              clearable
              placeholder="可选"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="task-center-view-select-popper"
            >
              <el-option
                v-for="department in publishDepartmentOptions"
                :key="department.id"
                :label="department.label"
                :value="department.id"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="执行人">
          <div data-testid="task-center-task-assignee" class="task-center-view__control-wrap">
            <el-select
              v-model="publishForm.assignee_user_id"
              class="task-center-view__full-select"
              :placeholder="assigneeSelectPlaceholder"
              :disabled="filteredPublishUserOptions.length === 0"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="task-center-view-select-popper"
            >
              <el-option
                v-for="user in filteredPublishUserOptions"
                :key="user.user_id"
                :label="user.label"
                :value="user.user_id"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="附件（可选）">
          <div data-testid="task-center-task-attachments">
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              :accept="ATTACHMENT_ACCEPT"
              :disabled="publishAttachmentUploading"
              :on-change="handlePublishDraftFileChange"
            >
              <el-button :loading="publishAttachmentUploading">选择附件</el-button>
            </el-upload>
          </div>
          <div v-if="publishDraftAttachments.length" class="task-center-view__draft-tags">
            <el-tag
              v-for="attachment in publishDraftAttachments"
              :key="attachment.id"
              closable
              class="task-center-view__draft-tag"
              @close="removePublishDraftAttachment(attachment.id)"
            >
              {{ attachment.original_filename }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="优先级">
          <div data-testid="task-center-task-priority" class="task-center-view__control-wrap">
            <el-select
              v-model="publishForm.priority"
              class="task-center-view__full-select"
              teleported
              :popper-options="{ strategy: 'fixed' }"
              popper-class="task-center-view-select-popper"
            >
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="urgent" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="截止时间">
          <div data-testid="task-center-task-due-date" class="task-center-view__control-wrap">
            <FilumDateTimePicker v-model="publishForm.due_date" class="task-center-view__date-picker" />
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="task-center-view__dialog-footer">
          <el-button @click="handleCancelTaskDialog">取消</el-button>
          <el-button
            type="primary"
            :loading="publishSubmitting"
            data-testid="task-center-task-submit"
            @click="handlePublishTask"
          >
            建立任务
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.task-center-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.task-center-view__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.task-center-view__subtitle {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.task-center-view__view-toggle--disabled {
  opacity: 0.5;
}

.task-center-view__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.task-center-view__master-detail {
  display: grid;
  grid-template-columns: minmax(280px, 35%) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.task-center-view__master {
  min-width: 0;
}

.task-center-view__detail {
  min-width: 0;
}

.task-center-view__section-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.task-center-view__section-header > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-center-view__section-header small {
  color: var(--filum-text-secondary);
  font-size: 12px;
}

.task-center-view__load-more {
  display: flex;
  justify-content: center;
  padding: 12px 0 4px;
}

.task-center-view__form {
  width: 100%;
}

.task-center-view__draft-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.task-center-view__control-wrap {
  width: 100%;
}

.task-center-view__full-select {
  width: 100%;
}

.task-center-view__date-picker {
  width: 100%;
}

.task-center-view__search {
  margin-top: 16px;
}

.task-center-view__dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.task-center-view__row--selected > td) {
  background: rgba(37, 99, 235, 0.08) !important;
}

@media (max-width: 1080px) {
  .task-center-view__master-detail {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.task-center-view-select-popper {
  z-index: 6000 !important;
}
</style>
