<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { listAttachments, uploadAttachment } from '@/api/attachments'
import AttachmentActions from '@/components/attachments/AttachmentActions.vue'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import { acceptTaskAssignment,
  addTaskWatchers,
  createTaskComment,
  delegateTaskAssignment,
  listTaskActivity,
  getTask,
  listTaskWatchers,
  rejectTaskAssignment,
  reviewTaskDeliverable,
  submitTaskDeliverable,
  updateTask,
  updateTaskStatus,
} from '@/api/tasks'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import { closeInstanceCapture, getWorkflowGraphInstance, listInstanceEvents } from '@/api/workflow-graph'
import TemplateAggregatePanel from '@/components/workflow/TemplateAggregatePanel.vue'
import CapturePanel from '@/components/workflow/CapturePanel.vue'
import VideoCaptureProgressPanel from '@/components/workflow/VideoCaptureProgressPanel.vue'
import VideoProductionPanel from '@/components/workflow/VideoProductionPanel.vue'
import VideoTrackingPanel from '@/components/workflow/VideoTrackingPanel.vue'
import BatchRunDashboard from '@/components/workflow/BatchRunDashboard.vue'
import { resolveActiveStepTaskId } from '@/domain/workflow-graph/activeStepTask'
import TaskDetailActionDialogs from '@/components/task-detail/TaskDetailActionDialogs.vue'
import TaskDetailHeaderBar from '@/components/task-detail/TaskDetailHeaderBar.vue'
import TaskDetailMetadataPanel from '@/components/task-detail/TaskDetailMetadataPanel.vue'
import { resolveStatusLabel } from '@/components/task-detail/task-detail-labels'
import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'
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
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type { WorkflowRunEventItem } from '@/types/workflowVideo'
import type {
  Attachment,
  Department,
  Task,
  TaskActivityEntry,
  TaskCenterUserOption,
  TaskStatus,
  TaskWatcher,
  User,
  WorkflowGraphInstanceDetail,
  WorkflowNodeInstanceSummary,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'
import { isCaptureClosed, resolveAggregateMode } from '@/utils/workflowVideoSchema'

interface Props {
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  emptyDescription?: string
}

type StatusAction = {
  label: string
  status: TaskStatus
  buttonType: 'primary' | 'warning' | 'success'
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
  delegateUserOptions: () => [],
  emptyDescription: '请从左侧选择任务',
})

const emit = defineEmits<{
  actionDone: []
  selectTask: [taskId: string]
}>()
const loading = ref(false)
const task = ref<Task | null>(null)
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
const taskAttachments = ref<Attachment[]>([])
const taskActivity = ref<TaskActivityEntry[]>([])
const taskWatchers = ref<TaskWatcher[]>([])
const graphInstance = ref<WorkflowGraphInstanceDetail | null>(null)
const workflowRunEvents = ref<WorkflowRunEventItem[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const watcherSubmitting = ref(false)
const watcherUserId = ref('')
const selectedTaskFile = ref<File | null>(null)
const commentFiles = ref<File[]>([])

const delegateForm = reactive({
  assignee_id: '',
  reason: '',
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
const selectedTask = computed(() => task.value)
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
const isGraphProductionRootTask = computed(
  () =>
    isGraphTemplateTask.value
    && selectedTaskMetadata.value.workflow_graph_root_task === true
    && graphRunKind.value === 'production',
)
const productionActiveStepTaskId = computed(() =>
  resolveActiveStepTaskId(graphInstance.value, {
    preferAssigneeUserId: authStore.user?.id ?? null,
  }),
)
const showProductionRootStepRouter = computed(
  () =>
    isGraphProductionRootTask.value
    && graphInstance.value !== null
    && productionActiveStepTaskId.value !== null
    && productionActiveStepTaskId.value !== selectedTask.value?.id,
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
const canAdminArchive = computed(() => {
  if (authStore.user?.role !== 'admin' || !selectedTask.value) {
    return false
  }
  const metadata = selectedTask.value.extra_metadata as Record<string, unknown> | undefined
  return metadata?.admin_archived !== true
})
const isSelectedTaskOverdue = computed(() => {
  const task = selectedTask.value
  if (!task?.due_date || task.status === 'done') {
    return false
  }
  return new Date(task.due_date).getTime() < Date.now()
})
const canManageDueDate = computed(() => authStore.isManagementRole)
const batchAggregateMode = computed(() => resolveAggregateMode(graphInstance.value?.context))
const captureClosed = computed(() => isCaptureClosed(graphInstance.value?.context))
const showCaptureProgressPanel = computed(
  () =>
    selectedTaskProfile.value.id === 'video_n2_aggregate'
    && graphInstance.value !== null
    && batchAggregateMode.value === 'batch',
)
const showVideoTrackingPanel = computed(
  () =>
    selectedTaskProfile.value.id === 'video_batch_root'
    && graphInstance.value !== null,
)
const showBatchRunDashboard = computed(
  () =>
    selectedTaskProfile.value.id === 'video_batch_root'
    && graphInstance.value !== null,
)
const showCloseCaptureButton = computed(
  () =>
    isGraphRootBatchTask.value
    && graphInstance.value !== null
    && batchAggregateMode.value === 'batch'
    && !captureClosed.value
    && canManageCaptureReject.value,
)
const showDetailHeaderActions = computed(() => {
  const profileId = selectedTaskProfile.value.id
  return profileId !== 'video_n1_capture'
    && profileId !== 'video_capture_assign'
    && profileId !== 'video_capture_schedule'
    && profileId !== 'video_n2_aggregate'
    && profileId !== 'video_batch_root'
})
const showCapturePanel = computed(
  () =>
    (selectedTaskProfile.value.id === 'video_n1_capture'
      || selectedTaskProfile.value.id === 'video_capture_assign'
      || selectedTaskProfile.value.id === 'video_capture_schedule')
    && selectedTask.value !== null,
)
const showVideoAggregatePanel = computed(
  () =>
    selectedTaskProfile.value.id === 'video_n2_aggregate'
    && batchAggregateMode.value === 'batch',
)
const videoProductionMode = computed((): 'single' | 'multi' | 'platform' => {
  const profileId = selectedTaskProfile.value.id
  if (profileId === 'video_production_multi') {
    return 'multi'
  }
  if (profileId === 'video_production_platform') {
    return 'platform'
  }
  return 'single'
})
const showVideoProductionPanel = computed(
  () =>
    (selectedTaskProfile.value.id === 'video_production_step'
      || selectedTaskProfile.value.id === 'video_production_multi'
      || selectedTaskProfile.value.id === 'video_production_platform')
    && selectedTaskProfile.value.submitMode === 'file'
    && selectedTask.value !== null,
)
const videoProductionPanelRef = ref<InstanceType<typeof VideoProductionPanel> | null>(null)
const closeCaptureSubmitting = ref(false)
const extendDueDateDialogVisible = ref(false)
const extendDueDateValue = ref<Date | null>(null)
const extendDueDateSubmitting = ref(false)
const usesCompactDetailTelemetry = computed(() => TASK_CENTER_V2_UI_ENABLED)
const compactRunEvents = computed(() =>
  usesCompactDetailTelemetry.value || usesVideoWorkflowLayout.value
    ? workflowRunEvents.value.slice(0, 3)
    : workflowRunEvents.value,
)
const usesCompactRunEventCards = computed(
  () => usesCompactDetailTelemetry.value || usesVideoWorkflowLayout.value,
)
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

function resolveTaskListRunLabel(task: Task): string {
  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  const graphLabel =
    graphInstance.value?.run_label
    ?? (typeof graphInstance.value?.context?.run_label === 'string'
      ? graphInstance.value.context.run_label
      : null)
  return resolveTaskRunLabel(task.title, metadata, graphLabel)
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

function resetCommentForm(): void {
  commentForm.content = ''
  commentForm.is_internal = false
  commentFiles.value = []
}

function resetDeliverableForm(): void {
  deliverableForm.summary = ''
}

async function refreshTaskRecord(taskId: string): Promise<void> {
  try {
    task.value = await getTask(taskId)
  } catch {
    // ignore — detail loaders will surface errors
  }
}

async function loadSelectedTaskDetails(taskId: string): Promise<void> {
  await refreshTaskRecord(taskId)
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
  const metadata = (task.value?.extra_metadata ?? {}) as Record<string, unknown>
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

async function loadUsers(): Promise<void> {
  if (authStore.isManagementRole) {
    users.value = await listUsers()
  } else if (authStore.user) {
    users.value = [authStore.user]
  }
}

async function loadDepartmentsIfNeeded(): Promise<void> {
  if (departments.value.length > 0) {
    return
  }
  try {
    const { listDepartments } = await import('@/api/departments')
    departments.value = await listDepartments()
  } catch {
    departments.value = []
  }
}

async function initialize(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([loadUsers(), loadDepartmentsIfNeeded()])
    const preferredTaskId = props.initialSelectedTaskId?.trim()
    if (preferredTaskId) {
      await loadSelectedTaskDetails(preferredTaskId)
    } else {
      task.value = null
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
      graphInstance.value = null
      workflowRunEvents.value = []
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function reloadAfterAction(): Promise<void> {
  if (!selectedTask.value) {
    emit('actionDone')
    return
  }
  await loadSelectedTaskDetails(selectedTask.value.id)
  emit('actionDone')
}

function handleTaskArchived(): void {
  emit('actionDone')
}

function openExtendDueDateDialog(): void {
  extendDueDateValue.value = selectedTask.value?.due_date ? new Date(selectedTask.value.due_date) : null
  extendDueDateDialogVisible.value = true
}

async function submitExtendDueDate(): Promise<void> {
  if (!selectedTask.value || !extendDueDateValue.value) {
    ElMessage.warning('请选择新的截止时间')
    return
  }
  extendDueDateSubmitting.value = true
  try {
    await updateTask(selectedTask.value.id, { due_date: extendDueDateValue.value.toISOString() })
    ElMessage.success('截止时间已更新')
    extendDueDateDialogVisible.value = false
    await reloadAfterAction()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    extendDueDateSubmitting.value = false
  }
}

async function handleCloseCapture(): Promise<void> {
  const instanceId = graphInstance.value?.id
  if (!instanceId) {
    return
  }
  closeCaptureSubmitting.value = true
  try {
    const result = await closeInstanceCapture(instanceId)
    ElMessage.success(result.message)
    await reloadAfterAction()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    closeCaptureSubmitting.value = false
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
    await reloadAfterAction()
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
    await reloadAfterAction()
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
    await reloadAfterAction()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    approvalSubmitting.value = false
  }
}

async function handleApprovalDecide(decision: 'approved' | 'rejected' | 'returned'): Promise<void> {
  if (decision === 'approved') {
    await handleDeliverableReview('approve', deliverableReviewForm.comment)
    return
  }

  const comment = rejectCommentText.value.trim()
  if (!comment) {
    ElMessage.error('驳回修改时必须填写原因')
    return
  }

  approvalSubmitting.value = true
  try {
    await reviewTaskDeliverable(selectedTask.value!.id, {
      action: 'return_for_rework',
      comment,
      quality_score: null,
    })
    ElMessage.success('已驳回，任务将重新激活')
    rejectCommentDialogVisible.value = false
    rejectCommentText.value = ''
    await reloadAfterAction()
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
    await reloadAfterAction()
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
    await reloadAfterAction()
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
    await reloadAfterAction()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    handshakeSubmitting.value = false
  }
}

onMounted(() => {
  void initialize()
})

watch(
  () => props.initialSelectedTaskId,
  async (nextTaskId) => {
    if (!nextTaskId) {
      task.value = null
      taskAttachments.value = []
      taskActivity.value = []
      taskWatchers.value = []
      graphInstance.value = null
      workflowRunEvents.value = []
      return
    }
    await loadSelectedTaskDetails(nextTaskId)
  },
  { immediate: true },
)
</script>

<template>
  <div class="task-detail-shell">
    <el-card shadow="never" class="page__detail" data-testid="tasks-detail-panel" v-loading="loading">
          <template #header>
            <TaskDetailHeaderBar
              :show-close-capture-button="showCloseCaptureButton"
              :close-capture-submitting="closeCaptureSubmitting"
              :show-detail-header-actions="showDetailHeaderActions"
              :can-decide-approval="canDecideApproval"
              :approval-submitting="approvalSubmitting"
              :can-review-deliverable="canReviewDeliverable"
              :use-video-production-review-more-menu="useVideoProductionReviewMoreMenu"
              :deliverable-review-comment="deliverableReviewForm.comment"
              :selected-task="selectedTask"
              :is-graph-handshake-task="isGraphHandshakeTask"
              :can-accept-task="canAcceptTask"
              :can-reject-task="canRejectTask"
              :can-delegate-task="canDelegateTask"
              :handshake-submitting="handshakeSubmitting"
              :next-status-action="nextStatusAction"
              :can-advance-selected-task-by-status="canAdvanceSelectedTaskByStatus"
              :status-submitting="statusSubmitting"
              :can-submit-deliverable="canSubmitDeliverable"
              :selected-task-profile="selectedTaskProfile"
              :video-production-panel-ref="videoProductionPanelRef"
              :deliverable-submitting="deliverableSubmitting"
              :uses-video-workflow-layout="usesVideoWorkflowLayout"
              :can-admin-archive="canAdminArchive"
              :graph-instance="graphInstance"
              :can-manage-capture-reject="canManageCaptureReject"
              :can-reject-production-step="canRejectProductionStep"
              @close-capture="handleCloseCapture"
              @approval-decide="handleApprovalDecide"
              @open-reject-dialog="openRejectDialog"
              @deliverable-review="handleDeliverableReview('approve', deliverableReviewForm.comment)"
              @open-rework-dialog="openReworkDialog"
              @accept-assignment="handleAcceptAssignment"
              @open-handshake-reject-dialog="openHandshakeRejectDialog"
              @open-delegate-dialog="openDelegateDialog"
              @status-transition="handleStatusTransition"
              @submit-deliverable="handleSubmitDeliverable"
              @action-done="reloadAfterAction"
              @task-archived="handleTaskArchived"
            />
          </template>

          <el-empty
            v-if="!selectedTask"
            :description="props.emptyDescription"
            data-testid="tasks-detail-empty"
          />

          <template v-if="selectedTask">
            <el-alert
              v-if="isSelectedTaskOverdue"
              type="warning"
              :closable="false"
              show-icon
              class="task-detail-shell__overdue-alert"
              data-testid="task-detail-overdue-alert"
            >
              <template #title>任务已逾期</template>
              逾期不阻断提交与验收。如需调整截止时间，请由管理员延期后继续推进。
              <div v-if="canManageDueDate" style="margin-top: 8px">
                <el-button size="small" type="warning" @click="openExtendDueDateDialog">延期…</el-button>
              </div>
            </el-alert>

            <TaskDetailMetadataPanel
              :task="selectedTask"
              :profile="selectedTaskProfile"
              :user-facing-state-label="selectedTaskUserFacingStateLabel"
              :user-facing-tag-type="selectedTaskUserFacingTagType"
              :handshake-state-label="handshakeStateLabel"
              :is-graph-handshake-task="isGraphHandshakeTask"
              :workflow-node-iteration="workflowNodeIteration"
              :workflow-deep-rejection-reason="workflowDeepRejectionReason"
              :latest-reject-reason="latestRejectReason"
              :latest-delegate-reason="latestDelegateReason"
              :latest-deliverable-summary="latestDeliverableSummary"
              :latest-deliverable-submitted-at="latestDeliverableSubmittedAt"
              :latest-review-quality-score="latestReviewQualityScore"
              :rework-count="reworkCount"
              :latest-rework-reason="latestReworkReason"
              :graph-parent-instance-id="graphParentInstanceId"
              :graph-run-kind="graphRunKind"
              :resolve-department-name="resolveDepartmentName"
              :resolve-user-label="resolveUserLabel"
              :resolve-run-label="resolveTaskListRunLabel"
            />

            <VideoTrackingPanel
              v-if="showVideoTrackingPanel && graphInstance"
              :graph-instance="graphInstance"
              :users="users"
              :can-manage-reject="canManageCaptureReject"
              @dispatched="reloadAfterAction"
              @rejected="reloadAfterAction"
            />
            <el-alert
              v-if="showProductionRootStepRouter"
              type="info"
              :closable="false"
              show-icon
              class="workflow-panel"
              data-testid="production-root-step-router"
            >
              <template #title>这是制作 Run 跟踪壳层</template>
              请打开当前步骤任务提交脚本、配音等交付物。
              <div style="margin-top: 8px">
                <el-button
                  type="primary"
                  size="small"
                  @click="emit('selectTask', productionActiveStepTaskId!)"
                >
                  打开当前步骤任务
                </el-button>
              </div>
            </el-alert>
            <BatchRunDashboard
              v-if="showBatchRunDashboard && graphInstance"
              :graph-instance="graphInstance"
              @open-task="(taskId: string) => emit('selectTask', taskId)"
            />
            <VideoCaptureProgressPanel
              v-if="showCaptureProgressPanel && graphInstance"
              :graph-instance="graphInstance"
            />
            <CapturePanel
              v-if="showCapturePanel && selectedTask"
              :task="selectedTask"
              :graph-instance="graphInstance"
              @submitted="reloadAfterAction"
            />
            <VideoProductionPanel
              v-if="showVideoProductionPanel && selectedTask"
              ref="videoProductionPanelRef"
              :task="selectedTask"
              :mode="videoProductionMode"
              @submitted="reloadAfterAction"
            />
            <TemplateAggregatePanel
              v-if="showVideoAggregatePanel && selectedTask"
              :task="selectedTask"
              :graph-instance="graphInstance"
              :users="users"
              :can-manage-reject="canManageCaptureReject"
              @finalized="reloadAfterAction"
              @rejected="reloadAfterAction"
            />

            <el-card
              v-if="workflowRunEvents.length > 0"
              shadow="never"
              class="page__run-events"
              :data-testid="usesCompactRunEventCards ? 'workflow-run-events-compact' : 'workflow-run-events'"
            >
              <template #header>
                <div class="page__header">
                  <strong>{{ usesCompactRunEventCards ? '最近事件' : '运行事件' }}</strong>
                  <router-link
                    v-if="usesCompactDetailTelemetry && selectedTask"
                    :to="{ name: 'task-center', query: { filter: 'stats', selected: selectedTask.id } }"
                  >
                    在任务统计中查看
                  </router-link>
                </div>
              </template>
              <el-timeline>
                <el-timeline-item
                  v-for="event in compactRunEvents"
                  :key="event.id"
                  :timestamp="formatDateTime(event.created_at)"
                >
                  {{ resolveRunEventLabel(event.event_type) }}
                  <span v-if="!usesCompactRunEventCards && typeof event.payload.reason === 'string'">
                    — {{ event.payload.reason }}
                  </span>
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
            <el-collapse
              v-if="graphInstance && !usesVideoWorkflowLayout && usesCompactDetailTelemetry"
              data-testid="task-detail-graph-collapse"
            >
              <el-collapse-item title="工作流节点追踪（完整日志见任务统计）" name="graph-nodes">
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
              </el-collapse-item>
            </el-collapse>
            <template v-else-if="graphInstance && !usesVideoWorkflowLayout">
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
        </el-card>

    <el-dialog v-model="extendDueDateDialogVisible" title="延期任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="新的截止时间" required>
          <FilumDateTimePicker v-model="extendDueDateValue" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="extendDueDateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="extendDueDateSubmitting" @click="submitExtendDueDate">
          确认延期
        </el-button>
      </template>
    </el-dialog>

    <TaskDetailActionDialogs
      v-model:reject-comment-dialog-visible="rejectCommentDialogVisible"
      v-model:reject-comment-text="rejectCommentText"
      v-model:rework-dialog-visible="reworkDialogVisible"
      v-model:rework-comment-text="reworkCommentText"
      v-model:handshake-reject-dialog-visible="handshakeRejectDialogVisible"
      v-model:handshake-reject-reason="handshakeRejectReason"
      v-model:delegate-dialog-visible="delegateDialogVisible"
      v-model:delegate-assignee-id="delegateForm.assignee_id"
      v-model:delegate-reason="delegateForm.reason"
      :approval-submitting="approvalSubmitting"
      :handshake-submitting="handshakeSubmitting"
      :delegate-candidate-options="delegateCandidateOptions"
      @confirm-reject="handleApprovalDecide('rejected')"
      @confirm-rework="handleDeliverableReview('return_for_rework', reworkCommentText)"
      @confirm-handshake-reject="handleRejectAssignment"
      @confirm-delegate="handleDelegateAssignment"
    />
  </div>
</template>


<style scoped>
.task-detail-shell {
  min-height: 100%;
}

.task-detail-shell__overdue-alert {
  margin-bottom: 16px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__detail {
  min-height: 100%;
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

.page__upload {
  margin-bottom: 12px;
}

.page__upload-button {
  margin-bottom: 16px;
}

.page__attachment-card {
  margin-bottom: 8px;
}

.page__attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__comments-collapse {
  margin-top: 16px;
}

.page__timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.page__timeline-text {
  margin: 0;
  color: #606266;
}

.page__inline-tag {
  margin-left: 8px;
}

.page__comment-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.page__comment-attachment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__node-timeline {
  width: 100%;
}

.page__node-card {
  margin-bottom: 8px;
}

.page__node-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__node-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page__node-meta {
  margin: 4px 0 0;
  color: #909399;
  font-size: 13px;
}

.page__node-meta--terminated {
  color: #f56c6c;
}

.page__run-events {
  margin-top: 16px;
}
</style>
