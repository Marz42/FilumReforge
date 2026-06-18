<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { listAttachments, uploadAttachment } from '@/api/attachments'
import AttachmentActions from '@/components/attachments/AttachmentActions.vue'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import { listDepartments } from '@/api/departments'
import { acceptTaskAssignment,
  addTaskWatchers,
  createTask,
  createTaskComment,
  delegateTaskAssignment,
  getTaskStatsSummary,
  getTaskWorkload,
  listTaskActivity,
  listTaskBoard,
  listTaskGantt,
  getTask,
  listTasks,
  listTaskWatchers,
  rejectTaskAssignment,
  reviewTaskDeliverable,
  submitTaskDeliverable,
  updateTaskStatus,
} from '@/api/tasks'
import { getWorkflowGraphInstance, listInstanceEvents } from '@/api/workflow-graph'
import BatchRunDashboard from '@/components/workflow/BatchRunDashboard.vue'
import TemplateAggregatePanel from '@/components/workflow/TemplateAggregatePanel.vue'
import VideoCapturePanel from '@/components/workflow/VideoCapturePanel.vue'
import VideoCaptureProgressPanel from '@/components/workflow/VideoCaptureProgressPanel.vue'
import VideoProductionPanel from '@/components/workflow/VideoProductionPanel.vue'
import VideoTrackingPanel from '@/components/workflow/VideoTrackingPanel.vue'
import TaskDetailMoreMenu from '@/components/task-detail/TaskDetailMoreMenu.vue'
import {
  isVideoWorkflowProfile,
  resolveTaskDetailProfile,
} from '@/domain/task-detail/profile'
import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'
import {
  resolveTaskUserFacingStateForTask,
  TASK_USER_FACING_STATE_LABELS,
  userFacingStateTagType,
} from '@/domain/task-detail/user-state'
import { decideStepRun } from '@/api/task-templates'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'
import type {
  Attachment,
  Department,
  Task,
  TaskActivityEntry,
  TaskBoardColumn,
  TaskGanttEntry,
  TaskPriority,
  TaskCenterUserOption,
  TaskStatus,
  TaskStatsSummary,
  TaskWatcher,
  TaskWorkloadRow,
  User,
  WorkflowGraphInstanceDetail,
  WorkflowNodeInstanceSummary,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  showCreateTaskComposer?: boolean
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  detailOnly?: boolean
  hideStats?: boolean
  hideViewToggle?: boolean
  externalViewMode?: 'list' | 'board' | 'gantt'
}

type StatusAction = {
  label: string
  status: TaskStatus
  buttonType: 'primary' | 'warning' | 'success'
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

const NEXT_STATUS_ACTIONS: Record<Exclude<TaskStatus, 'done'>, StatusAction> = {
  todo: {
    label: '开始处理',
    status: 'doing',
    buttonType: 'primary',
  },
  doing: {
    label: '提交评审',
    status: 'review',
    buttonType: 'warning',
  },
  review: {
    label: '标记完成',
    status: 'done',
    buttonType: 'success',
  },
}

const authStore = useAuthStore()
const props = withDefaults(defineProps<Props>(), {
  showCreateTaskComposer: true,
  delegateUserOptions: () => [],
  detailOnly: false,
  hideStats: false,
  hideViewToggle: false,
})
const loading = ref(false)
const submitting = ref(false)
const taskAttachmentUploading = ref(false)
const commentSubmitting = ref(false)
const deliverableSubmitting = ref(false)
const statusSubmitting = ref(false)
const approvalSubmitting = ref(false)
const handshakeSubmitting = ref(false)
const rejectCommentDialogVisible = ref(false)
const rejectCommentText = ref('')
const reworkDialogVisible = ref(false)
const reworkCommentText = ref('')
const handshakeRejectDialogVisible = ref(false)
const handshakeRejectReason = ref('')
const delegateDialogVisible = ref(false)
const dialogVisible = ref(false)
const tasks = ref<Task[]>([])
const taskBoard = ref<TaskBoardColumn[]>([])
const taskGantt = ref<TaskGanttEntry[]>([])
const taskAttachments = ref<Attachment[]>([])
const taskActivity = ref<TaskActivityEntry[]>([])
const taskWatchers = ref<TaskWatcher[]>([])
const graphInstance = ref<WorkflowGraphInstanceDetail | null>(null)
const workflowRunEvents = ref<WorkflowRunEventItem[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const statsSummary = ref<TaskStatsSummary | null>(null)
const workloadRows = ref<TaskWorkloadRow[]>([])
const selectedTaskId = ref('')
const viewMode = ref<'list' | 'board' | 'gantt'>('list')
const watcherSubmitting = ref(false)
const watcherUserId = ref('')
const selectedTaskFile = ref<File | null>(null)
const commentFiles = ref<File[]>([])

const delegateForm = reactive({
  assignee_id: '',
  reason: '',
})

const form = reactive({
  title: '',
  description: '',
  assignee_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
})

const commentForm = reactive({
  content: '',
  is_internal: false,
})

const deliverableForm = reactive({
  summary: '',
})

const deliverableReviewForm = reactive({
  comment: '',
  quality_score: 5 as number | null,
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
const selectedTask = computed(() => tasks.value.find((task) => task.id === selectedTaskId.value) ?? null)
const selectedTaskMetadata = computed<Record<string, unknown>>(
  () => (selectedTask.value?.extra_metadata as Record<string, unknown> | undefined) ?? {},
)
const isGraphHandshakeTask = computed(() => {
  const task = selectedTask.value
  if (!task || task.source_type !== 'manual') {
    return false
  }

  return typeof selectedTaskMetadata.value.workflow_graph_instance_id === 'string'
    && typeof selectedTaskMetadata.value.workflow_node_instance_id === 'string'
})
const currentHandshakeState = computed<'assigned' | 'accepted' | 'rejected' | null>(() => {
  if (!isGraphHandshakeTask.value) {
    return null
  }

  const value = selectedTaskMetadata.value.workflow_handshake_state
  if (value === 'assigned' || value === 'accepted' || value === 'rejected') {
    return value
  }
  if (selectedTask.value?.status === 'todo') {
    return 'accepted'
  }
  return null
})
const handshakeStateLabel = computed(() => {
  if (currentHandshakeState.value === 'assigned') {
    return '待确认'
  }
  if (currentHandshakeState.value === 'accepted') {
    return '已接受待开工'
  }
  if (currentHandshakeState.value === 'rejected') {
    return '已拒绝待调整'
  }
  return '—'
})
const delegateCandidateOptions = computed(() => {
  const currentAssigneeId = selectedTask.value?.assignee_id ?? ''
  if (props.delegateUserOptions.length > 0) {
    return props.delegateUserOptions.filter((option) => option.user_id !== currentAssigneeId)
  }

  return users.value
    .filter((user) => user.status === 'active' && user.id !== currentAssigneeId)
    .map((user) => ({
      user_id: user.id,
      email: user.email,
      real_name: null,
      department_id: null,
      department_name: null,
      label: user.email,
    }))
})
const watcherOptions = computed(() =>
  users.value.filter(
    (user) =>
      user.status === 'active' &&
      !taskWatchers.value.some((watcher) => watcher.user_id === user.id),
  ),
)
const nextStatusAction = computed(() => {
  const task = selectedTask.value
  if (!task || task.status === 'done') {
    return null
  }

  return NEXT_STATUS_ACTIONS[task.status]
})
const canAdvanceSelectedTask = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user) {
    return false
  }

  return authStore.isManagementRole || user.id === task.assignee_id || user.id === task.creator_id
})

const canAdvanceSelectedTaskByStatus = computed(() => {
  const task = selectedTask.value
  if (!task || !canAdvanceSelectedTask.value) {
    return false
  }

  if (isGraphHandshakeTask.value && task.status === 'todo') {
    return currentHandshakeState.value === 'accepted'
  }

  if (task.source_type === 'manual' && !isApprovalTask.value && task.status !== 'todo') {
    return false
  }

  return true
})

const canHandleHandshakeAction = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || !isGraphHandshakeTask.value || task.status !== 'todo') {
    return false
  }

  return authStore.isManagementRole || user.id === task.assignee_id
})

const canAcceptTask = computed(
  () => canHandleHandshakeAction.value && currentHandshakeState.value === 'assigned',
)

const canRejectTask = computed(
  () => canHandleHandshakeAction.value && currentHandshakeState.value !== 'rejected',
)

const canDelegateTask = computed(
  () => canHandleHandshakeAction.value && currentHandshakeState.value !== 'rejected' && delegateCandidateOptions.value.length > 0,
)

const canSubmitDeliverable = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || task.status !== 'doing') {
    return false
  }

  return authStore.isManagementRole || user.id === task.assignee_id
})

const isApprovalTask = computed(() => {
  const meta = selectedTask.value?.extra_metadata as Record<string, unknown> | undefined
  const approvalType = meta?.template_step_approval_type
  return typeof approvalType === 'string' && approvalType !== 'none' && approvalType !== ''
})

const canDecideApproval = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || !isApprovalTask.value) return false
  if (task.status !== 'review') return false
  return authStore.isManagementRole || user.id === task.assignee_id || user.id === task.creator_id
})
const canReviewDeliverable = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || isApprovalTask.value || task.status !== 'review') {
    return false
  }

  return authStore.isManagementRole || user.id === task.creator_id
})
const useVideoProductionReviewMoreMenu = computed(
  () =>
    selectedTaskProfile.value.id === 'video_production_step'
    && selectedTaskProfile.value.submitMode === 'review',
)
const canRejectProductionStep = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || !useVideoProductionReviewMoreMenu.value || task.status !== 'review') {
    return false
  }
  return authStore.isManagementRole || user.id === task.assignee_id || user.id === task.creator_id
})
const canManageCaptureReject = computed(() => {
  const user = authStore.user
  const instance = graphInstance.value
  if (!user || !instance) {
    return false
  }
  if (authStore.isManagementRole) {
    return true
  }
  if (user.id === instance.initiator_user_id) {
    return true
  }
  const context = instance.context ?? {}
  const managerId = context.manager_user_id
  if (managerId != null && String(managerId) === user.id) {
    return true
  }
  const aggregateNode = instance.node_instances?.find(
    (node) => node.node_key.startsWith('N2_') || node.node_key.includes('AGGREGATE'),
  )
  if (aggregateNode?.assignee_user_id === user.id) {
    return true
  }
  return false
})
const completionRateText = computed(() => formatRate(statsSummary.value?.completion_rate ?? 0))
const overdueRateText = computed(() => formatRate(statsSummary.value?.overdue_rate ?? 0))
const latestDeliverableSummary = computed(() => {
  const value = selectedTaskMetadata.value.latest_deliverable_summary
  return typeof value === 'string' && value.trim() ? value : '—'
})
const latestDeliverableSubmittedAt = computed(() => {
  const value = selectedTaskMetadata.value.latest_deliverable_submitted_at
  return typeof value === 'string' ? value : null
})
const latestReworkReason = computed(() => {
  const value = selectedTaskMetadata.value.latest_rework_reason
  return typeof value === 'string' && value.trim() ? value : '—'
})
const latestRejectReason = computed(() => {
  const value = selectedTaskMetadata.value.latest_reject_reason
  return typeof value === 'string' && value.trim() ? value : '—'
})
const latestDelegateReason = computed(() => {
  const value = selectedTaskMetadata.value.latest_delegate_reason
  return typeof value === 'string' && value.trim() ? value : '—'
})
const latestReviewQualityScore = computed(() => {
  const value = selectedTaskMetadata.value.latest_review_quality_score
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
})
const reworkCount = computed(() => {
  const value = selectedTaskMetadata.value.rework_count
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? 0 : parsed
  }
  return 0
})
const workflowNodeIteration = computed(() => {
  const value = selectedTaskMetadata.value.workflow_node_iteration
  if (typeof value === 'number') return value
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10)
    return Number.isNaN(parsed) ? 1 : parsed
  }
  return 1
})
const workflowDeepRejectionReason = computed(() => {
  const value = selectedTaskMetadata.value.workflow_deep_rejection_reason
  return typeof value === 'string' && value.trim() ? value : null
})
const isGraphTemplateTask = computed(() => {
  const task = selectedTask.value
  if (!task || task.source_type !== 'template') {
    return false
  }
  return typeof selectedTaskMetadata.value.workflow_graph_instance_id === 'string'
})
const graphTemplateNodeKey = computed(() => {
  const value = selectedTaskMetadata.value.template_node_key
  return typeof value === 'string' ? value : ''
})
const graphRunKind = computed(() => {
  const value = selectedTaskMetadata.value.run_kind
  return typeof value === 'string' ? value : ''
})
const isGraphRootBatchTask = computed(
  () =>
    isGraphTemplateTask.value
    && selectedTaskMetadata.value.workflow_graph_root_task === true
    && graphRunKind.value === 'batch',
)
const selectedTaskProfile = computed(() =>
  resolveTaskDetailProfile(selectedTask.value, { currentUserId: authStore.user?.id }),
)
const selectedTaskUserFacingState = computed(() => {
  if (!selectedTask.value) {
    return null
  }
  return resolveTaskUserFacingStateForTask(selectedTask.value, authStore.user?.id)
})
const selectedTaskUserFacingStateLabel = computed(() => {
  const state = selectedTaskUserFacingState.value
  return state ? TASK_USER_FACING_STATE_LABELS[state] : '—'
})
const selectedTaskUserFacingTagType = computed(() => {
  const state = selectedTaskUserFacingState.value
  return state ? userFacingStateTagType(state) : 'info'
})
const usesVideoWorkflowLayout = computed(() => isVideoWorkflowProfile(selectedTaskProfile.value))
const showCaptureProgressPanel = computed(
  () => selectedTaskProfile.value.id === 'video_n2_aggregate' && graphInstance.value !== null,
)
const showVideoTrackingPanel = computed(
  () => selectedTaskProfile.value.id === 'video_batch_root' && graphInstance.value !== null,
)
const showDetailHeaderActions = computed(() => {
  const profileId = selectedTaskProfile.value.id
  return profileId !== 'video_n1_capture'
    && profileId !== 'video_n2_aggregate'
    && profileId !== 'video_batch_root'
})
const showVideoCapturePanel = computed(
  () => selectedTaskProfile.value.id === 'video_n1_capture',
)
const showVideoAggregatePanel = computed(
  () => selectedTaskProfile.value.id === 'video_n2_aggregate',
)
const showVideoProductionPanel = computed(
  () =>
    selectedTaskProfile.value.id === 'video_production_step'
    && selectedTaskProfile.value.submitMode === 'file'
    && selectedTask.value !== null,
)
const videoProductionPanelRef = ref<InstanceType<typeof VideoProductionPanel> | null>(null)
const showBatchRunDashboard = computed(() => isGraphRootBatchTask.value && graphInstance.value !== null)
const graphParentInstanceId = computed(() => {
  if (graphInstance.value?.parent_instance_id) {
    return graphInstance.value.parent_instance_id
  }
  const parentId = graphInstance.value?.context?.parent_instance_id
  return typeof parentId === 'string' ? parentId : null
})
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

function normalizeTagType(value: '' | 'info' | 'warning' | 'success' | 'danger'): 'info' | 'warning' | 'success' | 'danger' | undefined {
  return value || undefined
}

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

const delegateUserLabelMap = computed(
  () => new Map(props.delegateUserOptions.map((option) => [option.user_id, option.label])),
)

function resolveUserLabel(userId: string, preferredLabel?: string | null): string {
  if (preferredLabel) {
    return preferredLabel
  }
  return (
    delegateUserLabelMap.value.get(userId) ??
    userEmailMap.value.get(userId) ??
    `用户 ${userId.slice(0, 8)}`
  )
}

function resolveNodeEngineStateLabel(state: WorkflowNodeInstanceSummary['engine_state']): string {
  const labels: Record<string, string> = {
    pending: '待激活',
    activated: '进行中',
    acknowledged: '已确认',
    completed: '已完成',
    terminated: '已终止',
  }
  return labels[state] ?? state
}

function resolveNodeEngineStateTagType(
  state: WorkflowNodeInstanceSummary['engine_state'],
): 'info' | 'primary' | 'success' | 'danger' | 'warning' {
  if (state === 'completed') return 'success'
  if (state === 'activated' || state === 'acknowledged') return 'primary'
  if (state === 'terminated') return 'danger'
  return 'info'
}

function formatNodeDuration(node: WorkflowNodeInstanceSummary): string {
  if (!node.activated_at) return '—'
  const end = node.completed_at ?? node.terminated_at
  if (!end) return '进行中'
  const ms = new Date(end).getTime() - new Date(node.activated_at).getTime()
  const minutes = Math.floor(ms / 60000)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时`
  return `${Math.floor(hours / 24)} 天`
}

function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}

function resolveTaskListRunLabel(task: Task): string {
  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  const graphLabel =
    graphInstance.value?.run_label
    ?? (typeof graphInstance.value?.context?.run_label === 'string'
      ? graphInstance.value.context.run_label
      : null)
  return resolveTaskRunLabel(task.title, metadata, graphLabel)
}

function formatRate(value: number): string {
  return `${Math.round(value * 100)}%`
}

function renderLogSummary(entry: TaskActivityEntry): string {
  const log = entry.log
  if (!log) {
    return ''
  }

  const detailAction = typeof log.detail.action === 'string' ? log.detail.action : null
  if (detailAction === 'submit_deliverable') {
    return '提交了交付物，等待验收'
  }
  if (detailAction === 'assigned') {
    return '发布了任务，等待执行人确认'
  }
  if (detailAction === 'accepted') {
    return '接受了任务，等待开工'
  }
  if (detailAction === 'rejected') {
    return `退回协商：${String(log.detail.reason ?? '请重新确认任务目标')}`
  }
  if (detailAction === 'delegated') {
    return `转办了任务：${String(log.detail.reason ?? '请由更合适的人继续处理')}`
  }
  if (detailAction === 'approve_completion') {
    const qualityScore = log.detail.quality_score
    return typeof qualityScore === 'number'
      ? `完成交付已通过验收，质量 ${qualityScore}/5`
      : '完成交付已通过验收'
  }
  if (detailAction === 'return_for_rework') {
    return `打回返工：${String(log.detail.comment ?? '请补充修改')}`
  }

  switch (log.action_type) {
    case 'created':
      return '创建了任务'
    case 'assigned':
      return '更新了执行人'
    case 'status_changed':
      return `状态从 ${resolveStatusLabel(log.from_status ?? 'todo')} 变更为 ${resolveStatusLabel(log.to_status ?? 'todo')}`
    case 'commented':
      return '添加了评论'
    case 'attachment_added':
      return `添加了附件：${String(log.detail.filename ?? '未命名文件')}`
    case 'due_date_changed':
      return '更新了截止时间'
    case 'closed':
      return '关闭了任务'
    default:
      return '更新了任务'
  }
}

function resetTaskForm(): void {
  form.title = ''
  form.description = ''
  form.assignee_id = authStore.user?.id ?? ''
  form.department_id = ''
  form.priority = 'medium'
  form.due_date = null
}

function resetCommentForm(): void {
  commentForm.content = ''
  commentForm.is_internal = false
  commentFiles.value = []
}

function resetDeliverableForm(): void {
  deliverableForm.summary = ''
}

async function ensureTaskInList(taskId: string): Promise<void> {
  if (tasks.value.some((task) => task.id === taskId)) {
    return
  }
  try {
    const task = await getTask(taskId)
    tasks.value = [task, ...tasks.value.filter((item) => item.id !== task.id)]
  } catch {
    // ignore — detail loaders will surface errors
  }
}

async function loadSelectedTaskDetails(taskId: string): Promise<void> {
  await ensureTaskInList(taskId)
  const [attachments, activity, watchers] = await Promise.all([
    listAttachments({
      target_type: 'task',
      target_id: taskId,
    }),
    listTaskActivity(taskId),
    listTaskWatchers(taskId),
  ])

  taskAttachments.value = attachments
  taskActivity.value = activity
  taskWatchers.value = watchers

  // 若为图引擎任务，并行加载节点实例
  const metadata = (tasks.value.find((t) => t.id === taskId)?.extra_metadata ?? {}) as Record<string, unknown>
  const instanceId = typeof metadata.workflow_graph_instance_id === 'string'
    ? metadata.workflow_graph_instance_id
    : null
  if (instanceId) {
    try {
      const [instance, eventsPage] = await Promise.all([
        getWorkflowGraphInstance(instanceId),
        listInstanceEvents(instanceId, { limit: 50 }),
      ])
      graphInstance.value = instance
      workflowRunEvents.value = eventsPage.items
    } catch {
      graphInstance.value = null
      workflowRunEvents.value = []
    }
  } else {
    graphInstance.value = null
    workflowRunEvents.value = []
  }
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    if (props.detailOnly) {
      tasks.value = []
      taskBoard.value = []
      taskGantt.value = []
      departments.value = []
      statsSummary.value = null
      workloadRows.value = []

      if (authStore.isManagementRole) {
        users.value = await listUsers()
      } else if (authStore.user) {
        users.value = [authStore.user]
      }

      const preferredTaskId = props.initialSelectedTaskId?.trim()
      if (preferredTaskId) {
        selectedTaskId.value = preferredTaskId
        await loadSelectedTaskDetails(preferredTaskId)
      } else {
        selectedTaskId.value = ''
        taskAttachments.value = []
        taskActivity.value = []
        taskWatchers.value = []
        graphInstance.value = null
      }
      return
    }

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

    if (selectedTaskId.value) {
      await loadSelectedTaskDetails(selectedTaskId.value)
    } else {
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleAddWatcher(): Promise<void> {
  if (!selectedTask.value || !watcherUserId.value) {
    ElMessage.warning('请选择关注人')
    return
  }

  watcherSubmitting.value = true
  try {
    taskWatchers.value = await addTaskWatchers(selectedTask.value.id, [watcherUserId.value])
    watcherUserId.value = ''
    ElMessage.success('关注人已更新')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    watcherSubmitting.value = false
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
  void loadSelectedTaskDetails(task.id)
}

function handleTaskFileChange(uploadFile: UploadFile): void {
  selectedTaskFile.value = uploadFile.raw ?? null
}

function handleTaskFileRemove(): void {
  selectedTaskFile.value = null
}

function beforeUploadAttachmentFile(raw: File): boolean {
  const err = validateAttachmentFile(raw)
  if (err) {
    ElMessage.error(err)
    return false
  }
  return true
}

function normalizeUploadFiles(uploadFiles: UploadFile[]): File[] {
  return uploadFiles.reduce<File[]>((files, uploadFile) => {
    if (uploadFile.raw) {
      files.push(uploadFile.raw)
    }
    return files
  }, [])
}

async function handleTaskAttachmentUpload(): Promise<void> {
  if (!selectedTask.value || !selectedTaskFile.value) {
    ElMessage.warning('请选择任务并上传文件')
    return
  }

  taskAttachmentUploading.value = true

  try {
    await uploadAttachment({
      file: selectedTaskFile.value,
      target_type: 'task',
      target_id: selectedTask.value.id,
      visibility: 'private',
    })

    ElMessage.success('任务资料附件已上传')
    selectedTaskFile.value = null
    await loadSelectedTaskDetails(selectedTask.value.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    taskAttachmentUploading.value = false
  }
}

function handleCommentFileChange(_: UploadFile, uploadFiles: UploadFile[]): void {
  commentFiles.value = normalizeUploadFiles(uploadFiles)
}

function handleCommentFileRemove(_: UploadFile, uploadFiles: UploadFile[]): void {
  commentFiles.value = normalizeUploadFiles(uploadFiles)
}

async function handleCommentSubmit(): Promise<void> {
  if (!selectedTask.value) {
    ElMessage.warning('请先选择任务')
    return
  }
  if (!commentForm.content.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }

  commentSubmitting.value = true

  try {
    await createTaskComment(selectedTask.value.id, {
      content: commentForm.content.trim(),
      is_internal: commentForm.is_internal,
      files: commentFiles.value,
    })

    ElMessage.success('评论已提交')
    resetCommentForm()
    await loadSelectedTaskDetails(selectedTask.value.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    commentSubmitting.value = false
  }
}

async function handleStatusTransition(): Promise<void> {
  if (!selectedTask.value || !nextStatusAction.value) {
    return
  }

  statusSubmitting.value = true

  try {
    await updateTaskStatus(selectedTask.value.id, nextStatusAction.value.status)
    ElMessage.success(`任务已更新为${resolveStatusLabel(nextStatusAction.value.status)}`)
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    statusSubmitting.value = false
  }
}

async function handleSubmitDeliverable(): Promise<void> {
  if (!selectedTask.value) {
    ElMessage.warning('请先选择任务')
    return
  }
  if (!deliverableForm.summary.trim()) {
    ElMessage.warning('请填写交付说明')
    return
  }

  deliverableSubmitting.value = true

  try {
    await submitTaskDeliverable(selectedTask.value.id, {
      summary: deliverableForm.summary.trim(),
    })
    ElMessage.success('交付物已提交，等待验收')
    resetDeliverableForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    deliverableSubmitting.value = false
  }
}

async function handleDeliverableReview(action: 'approve' | 'return_for_rework', comment?: string): Promise<void> {
  if (!selectedTask.value) {
    return
  }

  approvalSubmitting.value = true
  try {
    await reviewTaskDeliverable(selectedTask.value.id, {
      action,
      comment: comment?.trim() || null,
      quality_score: action === 'approve' ? deliverableReviewForm.quality_score : null,
    })
    ElMessage.success(action === 'approve' ? '验收已通过' : '任务已打回返工')
    reworkDialogVisible.value = false
    reworkCommentText.value = ''
    if (action === 'approve') {
      deliverableReviewForm.comment = ''
      deliverableReviewForm.quality_score = 5
    }
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    approvalSubmitting.value = false
  }
}

async function handleApprovalDecide(decision: 'approved' | 'rejected' | 'returned'): Promise<void> {
  const task = selectedTask.value
  if (!task) return
  const meta = task.extra_metadata as Record<string, unknown>
  const templateId = meta?.template_id as string | undefined
  const instanceId = meta?.template_instance_id as string | undefined
  const stepRunId = meta?.template_step_run_id as string | undefined
  if (!templateId || !instanceId || !stepRunId) {
    ElMessage.error('无法获取模板审核上下文，请联系管理员')
    return
  }

  approvalSubmitting.value = true
  try {
    const comment = rejectCommentText.value.trim() || undefined
    await decideStepRun(templateId, instanceId, stepRunId, decision, comment)
    ElMessage.success(decision === 'approved' ? '已审核通过' : '已驳回，步骤将重新激活')
    rejectCommentDialogVisible.value = false
    rejectCommentText.value = ''
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    approvalSubmitting.value = false
  }
}

function openRejectDialog(): void {
  rejectCommentText.value = ''
  rejectCommentDialogVisible.value = true
}

function openHandshakeRejectDialog(): void {
  handshakeRejectReason.value = ''
  handshakeRejectDialogVisible.value = true
}

function openDelegateDialog(): void {
  delegateForm.assignee_id = delegateCandidateOptions.value[0]?.user_id ?? ''
  delegateForm.reason = ''
  delegateDialogVisible.value = true
}

function openReworkDialog(): void {
  reworkCommentText.value = ''
  reworkDialogVisible.value = true
}

async function handleAcceptAssignment(): Promise<void> {
  if (!selectedTask.value) {
    return
  }

  handshakeSubmitting.value = true

  try {
    await acceptTaskAssignment(selectedTask.value.id)
    ElMessage.success('任务已接受，可以开始处理')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    handshakeSubmitting.value = false
  }
}

async function handleRejectAssignment(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  if (!handshakeRejectReason.value.trim()) {
    ElMessage.warning('请填写退回协商原因')
    return
  }

  handshakeSubmitting.value = true

  try {
    await rejectTaskAssignment(selectedTask.value.id, {
      reason: handshakeRejectReason.value.trim(),
    })
    ElMessage.success('任务已退回协商')
    handshakeRejectDialogVisible.value = false
    handshakeRejectReason.value = ''
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    handshakeSubmitting.value = false
  }
}

async function handleDelegateAssignment(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  if (!delegateForm.assignee_id) {
    ElMessage.warning('请选择转办目标')
    return
  }
  if (!delegateForm.reason.trim()) {
    ElMessage.warning('请填写转办原因')
    return
  }

  handshakeSubmitting.value = true

  try {
    await delegateTaskAssignment(selectedTask.value.id, {
      assignee_id: delegateForm.assignee_id,
      reason: delegateForm.reason.trim(),
    })
    ElMessage.success('任务已转办，等待新执行人确认')
    delegateDialogVisible.value = false
    delegateForm.assignee_id = ''
    delegateForm.reason = ''
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    handshakeSubmitting.value = false
  }
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
  async (nextTaskId) => {
    if (!nextTaskId) {
      if (props.detailOnly) {
        selectedTaskId.value = ''
        taskAttachments.value = []
        taskActivity.value = []
        taskWatchers.value = []
        graphInstance.value = null
      }
      return
    }
    selectedTaskId.value = nextTaskId
    await loadSelectedTaskDetails(nextTaskId)
  },
)

watch(
  () => tasks.value,
  async (taskList) => {
    const preferred = props.initialSelectedTaskId?.trim()
    if (!preferred || !taskList.some((task) => task.id === preferred)) {
      return
    }
    if (selectedTaskId.value === preferred) {
      return
    }
    selectedTaskId.value = preferred
    await loadSelectedTaskDetails(preferred)
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
      <el-col v-if="!props.detailOnly" :xs="24" :xl="12">
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
                  {{ resolveUserLabel(row.assignee_id) }}
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
                    <span>{{ resolveUserLabel(task.assignee_id) }}</span>
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
                  {{ resolveUserLabel(row.task.assignee_id) }}
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

      <el-col :xs="24" :xl="props.detailOnly ? 24 : 12">
        <el-card shadow="never" class="page__detail" data-testid="tasks-detail-panel">
          <template #header>
            <div class="page__header">
              <span>任务协同详情</span>
              <div v-if="showDetailHeaderActions" style="display: flex; gap: 8px; align-items: center">
                <template v-if="canDecideApproval">
                  <el-button
                    type="success"
                    :loading="approvalSubmitting"
                    @click="handleApprovalDecide('approved')"
                  >
                    审核通过
                  </el-button>
                  <el-button
                    type="danger"
                    :loading="approvalSubmitting"
                    @click="openRejectDialog"
                  >
                    驳回修改
                  </el-button>
                </template>
                <template v-else-if="canReviewDeliverable">
                  <el-button
                    type="success"
                    :loading="approvalSubmitting"
                    @click="handleDeliverableReview('approve', deliverableReviewForm.comment)"
                  >
                    验收通过
                  </el-button>
                  <el-button
                    v-if="!useVideoProductionReviewMoreMenu"
                    type="danger"
                    :loading="approvalSubmitting"
                    @click="openReworkDialog"
                  >
                    打回返工
                  </el-button>
                </template>
                <template v-else-if="selectedTask && isGraphHandshakeTask && selectedTask.status === 'todo'">
                  <el-button
                    v-if="canAcceptTask"
                    type="primary"
                    :loading="handshakeSubmitting"
                    @click="handleAcceptAssignment"
                  >
                    接受任务
                  </el-button>
                  <el-button
                    v-if="canRejectTask"
                    type="danger"
                    plain
                    :loading="handshakeSubmitting"
                    @click="openHandshakeRejectDialog"
                  >
                    退回协商
                  </el-button>
                  <el-button
                    v-if="canDelegateTask"
                    type="warning"
                    plain
                    :loading="handshakeSubmitting"
                    @click="openDelegateDialog"
                  >
                    转办
                  </el-button>
                  <el-button
                    v-if="nextStatusAction && canAdvanceSelectedTaskByStatus"
                    :type="nextStatusAction.buttonType"
                    :loading="statusSubmitting"
                    @click="handleStatusTransition"
                  >
                    {{ nextStatusAction.label }}
                  </el-button>
                </template>
                <el-button
                  v-else-if="canSubmitDeliverable && selectedTaskProfile.submitMode === 'file'"
                  type="primary"
                  :loading="videoProductionPanelRef?.submitting ?? false"
                  data-testid="video-production-header-submit"
                  @click="videoProductionPanelRef?.submit()"
                >
                  上传并提交
                </el-button>
                <el-button
                  v-else-if="canSubmitDeliverable"
                  type="warning"
                  :loading="deliverableSubmitting"
                  @click="handleSubmitDeliverable"
                >
                  提交交付物
                </el-button>
                <el-button
                  v-else-if="selectedTask && nextStatusAction && canAdvanceSelectedTaskByStatus"
                  :type="nextStatusAction.buttonType"
                  :loading="statusSubmitting"
                  @click="handleStatusTransition"
                >
                  {{ nextStatusAction.label }}
                </el-button>
              </div>
              <TaskDetailMoreMenu
                v-if="selectedTask && usesVideoWorkflowLayout"
                :profile="selectedTaskProfile"
                :task="selectedTask"
                :graph-instance="graphInstance"
                :can-manage-capture-reject="canManageCaptureReject"
                :can-reject-production="canRejectProductionStep"
                @action-done="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
              />
            </div>
          </template>

          <el-empty
            v-if="props.detailOnly && !selectedTask"
            description="请从左侧选择任务"
            data-testid="tasks-detail-empty"
          />

          <template v-if="selectedTask">
            <div
              v-if="selectedTaskProfile.compactMetadata"
              class="page__compact-meta"
              data-testid="task-detail-compact-meta"
            >
              <el-space wrap>
                <span>
                  用户态
                  <el-tag :type="normalizeTagType(selectedTaskUserFacingTagType)" effect="plain">
                    {{ selectedTaskUserFacingStateLabel }}
                  </el-tag>
                </span>
                <span>截止时间 {{ formatDateTime(selectedTask.due_date) }}</span>
                <span>所属部门 {{ resolveDepartmentName(selectedTask.department_id) }}</span>
                <span>Run {{ resolveTaskListRunLabel(selectedTask) }}</span>
                <span>执行人 {{ resolveUserLabel(selectedTask.assignee_id) }}</span>
              </el-space>
            </div>

            <el-descriptions v-if="!selectedTaskProfile.compactMetadata" :column="1" border>
              <el-descriptions-item label="任务标题">
                {{ selectedTask.title }}
              </el-descriptions-item>
              <el-descriptions-item label="执行人">
                {{ resolveUserLabel(selectedTask.assignee_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="normalizeTagType(STATUS_TAG_TYPES[selectedTask.status])" effect="plain">
                  {{ resolveStatusLabel(selectedTask.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="优先级">
                <el-tag :type="normalizeTagType(PRIORITY_TAG_TYPES[selectedTask.priority])" effect="plain">
                  {{ resolvePriorityLabel(selectedTask.priority) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="所属部门">
                {{ resolveDepartmentName(selectedTask.department_id) }}
              </el-descriptions-item>
              <el-descriptions-item label="截止时间">
                {{ formatDateTime(selectedTask.due_date) }}
              </el-descriptions-item>
              <el-descriptions-item label="任务描述">
                {{ selectedTask.description || '—' }}
              </el-descriptions-item>
              <el-descriptions-item v-if="!selectedTaskProfile.hideHandshakeFields" label="握手状态">
                {{ handshakeStateLabel }}
              </el-descriptions-item>
              <el-descriptions-item v-if="!selectedTaskProfile.hideHandshakeFields && isGraphHandshakeTask && workflowNodeIteration > 1" label="迭代版本">
                V{{ workflowNodeIteration }}（系统深度打回重放）
              </el-descriptions-item>
              <el-descriptions-item v-if="isGraphHandshakeTask && workflowDeepRejectionReason" label="打回原因">
                {{ workflowDeepRejectionReason }}
              </el-descriptions-item>
              <el-descriptions-item label="最近协商原因">
                {{ latestRejectReason }}
              </el-descriptions-item>
              <el-descriptions-item label="最近转办原因">
                {{ latestDelegateReason }}
              </el-descriptions-item>
              <el-descriptions-item label="最新交付说明">
                {{ latestDeliverableSummary }}
              </el-descriptions-item>
              <el-descriptions-item label="最近提交时间">
                {{ formatDateTime(latestDeliverableSubmittedAt) }}
              </el-descriptions-item>
              <el-descriptions-item label="完成质量评分">
                {{ latestReviewQualityScore ? `${latestReviewQualityScore}/5` : '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="返工次数">
                {{ reworkCount }}
              </el-descriptions-item>
              <el-descriptions-item label="最近返工原因">
                {{ latestReworkReason }}
              </el-descriptions-item>
              <el-descriptions-item v-if="graphParentInstanceId" label="所属批次">
                实例 {{ graphParentInstanceId.slice(0, 8) }}…
              </el-descriptions-item>
              <el-descriptions-item v-if="graphRunKind" label="运行类型">
                {{ graphRunKind === 'batch' ? '批次 Run' : graphRunKind === 'production' ? '制作 Run' : graphRunKind }}
              </el-descriptions-item>
            </el-descriptions>

            <VideoTrackingPanel
              v-if="showVideoTrackingPanel && graphInstance"
              :graph-instance="graphInstance"
              :users="users"
              :can-manage-reject="canManageCaptureReject"
              @dispatched="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
              @rejected="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
            />
            <VideoCaptureProgressPanel
              v-if="showCaptureProgressPanel && graphInstance"
              :graph-instance="graphInstance"
            />
            <BatchRunDashboard
              v-if="showBatchRunDashboard"
              :graph-instance="graphInstance"
              @open-task="(taskId) => { selectedTaskId = taskId; void loadSelectedTaskDetails(taskId) }"
            />
            <VideoCapturePanel
              v-if="showVideoCapturePanel && selectedTask"
              :task="selectedTask"
              :graph-instance="graphInstance"
              @submitted="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
            />
            <VideoProductionPanel
              v-if="showVideoProductionPanel && selectedTask"
              ref="videoProductionPanelRef"
              :task="selectedTask"
              @submitted="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
            />
            <TemplateAggregatePanel
              v-if="showVideoAggregatePanel && selectedTask"
              :task="selectedTask"
              :graph-instance="graphInstance"
              :users="users"
              :can-manage-reject="canManageCaptureReject"
              @finalized="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
              @rejected="() => selectedTask && loadSelectedTaskDetails(selectedTask.id)"
            />

            <el-card
              v-if="workflowRunEvents.length > 0 && !usesVideoWorkflowLayout"
              shadow="never"
              class="page__run-events"
              data-testid="workflow-run-events"
            >
              <template #header><strong>运行事件</strong></template>
              <el-timeline>
                <el-timeline-item
                  v-for="event in workflowRunEvents"
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

            <el-card
              v-else-if="workflowRunEvents.length > 0 && usesVideoWorkflowLayout"
              shadow="never"
              class="page__run-events"
              data-testid="workflow-run-events-compact"
            >
              <template #header><strong>最近事件</strong></template>
              <el-timeline>
                <el-timeline-item
                  v-for="event in workflowRunEvents.slice(0, 3)"
                  :key="event.id"
                  :timestamp="formatDateTime(event.created_at)"
                >
                  {{ resolveRunEventLabel(event.event_type) }}
                </el-timeline-item>
              </el-timeline>
            </el-card>

            <template v-if="!selectedTaskProfile.hideDeliverable">
            <el-divider>交付与验收</el-divider>

            <el-form v-if="canSubmitDeliverable" label-position="top">
              <el-form-item label="交付说明">
                <el-input
                  v-model="deliverableForm.summary"
                  type="textarea"
                  :rows="4"
                  placeholder="说明本次交付内容、完成情况与需要验收的要点"
                />
              </el-form-item>
            </el-form>

            <el-form v-else-if="canReviewDeliverable" label-position="top">
              <el-form-item label="验收评价（可选）">
                <el-input
                  v-model="deliverableReviewForm.comment"
                  type="textarea"
                  :rows="3"
                  placeholder="补充本次验收结论，便于留痕"
                />
              </el-form-item>
              <el-form-item label="完成质量评分">
                <el-select v-model="deliverableReviewForm.quality_score" placeholder="可选">
                  <el-option label="5 分" :value="5" />
                  <el-option label="4 分" :value="4" />
                  <el-option label="3 分" :value="3" />
                  <el-option label="2 分" :value="2" />
                  <el-option label="1 分" :value="1" />
                </el-select>
              </el-form-item>
            </el-form>

            </template>

            <template v-if="!selectedTaskProfile.hideWatchers">
            <el-divider>关注人与抄送</el-divider>

            <div class="page__watchers">
              <el-space wrap>
                <el-tag
                  v-for="watcher in taskWatchers"
                  :key="watcher.id"
                  effect="plain"
                  type="info"
                >
                  {{ resolveUserLabel(watcher.user_id) }}
                </el-tag>
              </el-space>

              <div class="page__watcher-form">
                <el-select
                  v-model="watcherUserId"
                  clearable
                  placeholder="添加关注人"
                  :disabled="watcherOptions.length === 0"
                >
                  <el-option
                    v-for="user in watcherOptions"
                    :key="user.id"
                    :label="user.email"
                    :value="user.id"
                  />
                </el-select>
                <el-button type="primary" :loading="watcherSubmitting" @click="handleAddWatcher">
                  添加
                </el-button>
              </div>
            </div>
            </template>

            <template v-if="!usesVideoWorkflowLayout">
            <el-divider>任务资料附件</el-divider>

            <div data-testid="tasks-attachment-upload">
              <el-upload
                class="page__upload"
                :auto-upload="false"
                :limit="1"
                :show-file-list="true"
                :accept="ATTACHMENT_ACCEPT"
                :before-upload="beforeUploadAttachmentFile"
                :on-change="handleTaskFileChange"
                :on-remove="handleTaskFileRemove"
              >
                <template #trigger>
                  <el-button>选择附件</el-button>
                </template>
              </el-upload>
            </div>

            <el-button
              type="primary"
              class="page__upload-button"
              :loading="taskAttachmentUploading"
              @click="handleTaskAttachmentUpload"
            >
              上传到任务
            </el-button>

            <el-empty v-if="taskAttachments.length === 0" description="暂无任务资料附件" />

            <el-space v-else direction="vertical" fill>
              <el-card
                v-for="attachment in taskAttachments"
                :key="attachment.id"
                shadow="never"
                class="page__attachment-card"
              >
                <div class="page__attachment-row">
                  <div>
                    <strong>{{ attachment.original_filename }}</strong>
                    <p>{{ attachment.mime_type }} · {{ attachment.size_bytes }} bytes</p>
                  </div>
                  <AttachmentActions
                    :attachment="attachment"
                    view-test-id="task-attachment-view"
                    download-test-id="task-attachment-download"
                  />
                </div>
              </el-card>
            </el-space>

            </template>

            <el-collapse v-if="selectedTaskProfile.collapseComments" class="page__comments-collapse">
              <el-collapse-item title="评论与留痕" name="comments">
                <el-form label-position="top">
                  <el-form-item label="评论内容">
                    <el-input
                      v-model="commentForm.content"
                      type="textarea"
                      :rows="4"
                      placeholder="请输入任务评论或协作说明"
                    />
                  </el-form-item>
                  <el-form-item v-if="authStore.isManagementRole" label="内部备注">
                    <el-switch v-model="commentForm.is_internal" />
                  </el-form-item>
                </el-form>
                <el-button type="primary" :loading="commentSubmitting" @click="handleCommentSubmit">
                  提交评论
                </el-button>
              </el-collapse-item>
            </el-collapse>

            <template v-else>
            <el-divider>评论与留痕</el-divider>

            <el-form label-position="top">
              <el-form-item label="评论内容">
                <el-input
                  v-model="commentForm.content"
                  type="textarea"
                  :rows="4"
                  placeholder="请输入任务评论或协作说明"
                />
              </el-form-item>
              <el-form-item v-if="authStore.isManagementRole" label="内部备注">
                <el-switch v-model="commentForm.is_internal" />
              </el-form-item>
              <el-form-item label="评论附件">
                <el-upload
                  :auto-upload="false"
                  multiple
                  :show-file-list="true"
                  :accept="ATTACHMENT_ACCEPT"
                  :before-upload="beforeUploadAttachmentFile"
                  :on-change="handleCommentFileChange"
                  :on-remove="handleCommentFileRemove"
                >
                  <template #trigger>
                    <el-button>选择评论附件</el-button>
                  </template>
                </el-upload>
              </el-form-item>
            </el-form>

            <el-button type="primary" :loading="commentSubmitting" @click="handleCommentSubmit">
              提交评论
            </el-button>

            <el-divider>活动时间线</el-divider>

            <!-- 图引擎节点板块（仅图任务显示） -->
            <template v-if="graphInstance && !usesVideoWorkflowLayout">
              <el-divider>工作流节点追踪</el-divider>
              <el-space direction="vertical" fill class="page__node-timeline" data-testid="tasks-graph-panel">
                <el-card
                  v-for="node in graphInstance.node_instances"
                  :key="node.id"
                  shadow="never"
                  class="page__node-card"
                >
                  <div class="page__node-card-header">
                    <div class="page__node-title">
                      <strong>{{ node.title }}</strong>
                      <el-tag v-if="node.iteration > 1" size="small" type="warning" effect="dark">
                        V{{ node.iteration }}
                      </el-tag>
                    </div>
                    <el-tag
                      :type="resolveNodeEngineStateTagType(node.engine_state)"
                      effect="plain"
                      size="small"
                    >
                      {{ resolveNodeEngineStateLabel(node.engine_state) }}
                    </el-tag>
                  </div>
                  <p class="page__node-meta">耗时：{{ formatNodeDuration(node) }}</p>
                  <p
                    v-if="node.engine_state === 'terminated'"
                    class="page__node-meta page__node-meta--terminated"
                  >
                    已被系统终止（or-join 撤权或深度打回）
                  </p>
                </el-card>
              </el-space>
            </template>

            <el-empty v-if="!usesVideoWorkflowLayout && taskActivity.length === 0" description="暂无活动记录" />

            <el-timeline v-else-if="!usesVideoWorkflowLayout">
              <el-timeline-item
                v-for="entry in taskActivity"
                :key="`${entry.entry_type}-${entry.created_at}`"
                :timestamp="formatDateTime(entry.created_at)"
                placement="top"
              >
                <el-card shadow="never">
                  <template v-if="entry.comment">
                    <div class="page__timeline-header">
                      <div>
                        <strong>{{ resolveUserLabel(entry.comment.user_id, entry.comment.author_label) }}</strong>
                        <el-tag
                          v-if="entry.comment.is_internal"
                          type="warning"
                          effect="plain"
                          class="page__inline-tag"
                        >
                          内部备注
                        </el-tag>
                      </div>
                      <el-tag type="primary" effect="plain">评论</el-tag>
                    </div>
                    <p class="page__timeline-text">{{ entry.comment.content }}</p>
                    <div
                      v-if="entry.comment.attachments.length > 0"
                      class="page__comment-attachments"
                    >
                      <div
                        v-for="attachment in entry.comment.attachments"
                        :key="attachment.id"
                        class="page__comment-attachment-row"
                      >
                        <span>{{ attachment.original_filename }}</span>
                        <AttachmentActions :attachment="attachment" />
                      </div>
                    </div>
                  </template>

                  <template v-else-if="entry.log">
                    <div class="page__timeline-header">
                      <strong>{{ resolveUserLabel(entry.log.operator_id, entry.log.operator_label) }}</strong>
                      <el-tag effect="plain">日志</el-tag>
                    </div>
                    <p class="page__timeline-text">{{ renderLogSummary(entry) }}</p>
                  </template>
                </el-card>
              </el-timeline-item>
            </el-timeline>

            </template>
          </template>

          <el-empty v-else description="点击左侧任务查看协同详情" />
        </el-card>
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

    <!-- 驳回审核对话框 -->
    <el-dialog v-model="rejectCommentDialogVisible" title="驳回说明" width="480px">
      <el-form label-position="top">
        <el-form-item label="驳回原因（可选）">
          <el-input
            v-model="rejectCommentText"
            type="textarea"
            :rows="3"
            placeholder="说明本次驳回的原因，便于执行人修改"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectCommentDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="approvalSubmitting" @click="handleApprovalDecide('rejected')">
          确认驳回
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reworkDialogVisible" title="返工说明" width="480px">
      <el-form label-position="top">
        <el-form-item label="返工原因（必填）">
          <el-input
            v-model="reworkCommentText"
            type="textarea"
            :rows="3"
            placeholder="请填写需要补充或修改的内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reworkDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="approvalSubmitting" @click="handleDeliverableReview('return_for_rework', reworkCommentText)">
          确认打回
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="handshakeRejectDialogVisible" title="退回协商" width="480px">
      <el-form label-position="top">
        <el-form-item label="协商原因（必填）">
          <el-input
            v-model="handshakeRejectReason"
            type="textarea"
            :rows="3"
            placeholder="请说明当前不能接单的原因，便于发起人调整"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handshakeRejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="handshakeSubmitting" @click="handleRejectAssignment">
          确认退回
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="delegateDialogVisible" title="转办任务" width="520px">
      <el-form label-position="top">
        <el-form-item label="转办给">
          <el-select v-model="delegateForm.assignee_id" placeholder="请选择转办目标">
            <el-option
              v-for="option in delegateCandidateOptions"
              :key="option.user_id"
              :label="option.label"
              :value="option.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转办原因（必填）">
          <el-input
            v-model="delegateForm.reason"
            type="textarea"
            :rows="3"
            placeholder="说明转办原因，便于新执行人理解背景"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="delegateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="handshakeSubmitting" @click="handleDelegateAssignment">
          确认转办
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

.page__detail,
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

.page__watchers {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page__watcher-form {
  display: flex;
  gap: 12px;
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

.page__compact-meta {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  font-size: 13px;
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
