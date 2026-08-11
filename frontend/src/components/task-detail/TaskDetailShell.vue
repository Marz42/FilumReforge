<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { addTaskWatchers } from '@/api/tasks'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import TaskDetailActionDialogs from '@/components/task-detail/TaskDetailActionDialogs.vue'
import TaskDetailActivityTimeline from '@/components/task-detail/TaskDetailActivityTimeline.vue'
import TaskDetailAttachmentsPanel from '@/components/task-detail/TaskDetailAttachmentsPanel.vue'
import TaskDetailCommentComposer from '@/components/task-detail/TaskDetailCommentComposer.vue'
import TaskDetailHeaderBar from '@/components/task-detail/TaskDetailHeaderBar.vue'
import TaskDetailContextPanel from '@/components/task-detail/TaskDetailContextPanel.vue'
import TaskDetailGraphTelemetry from '@/components/task-detail/TaskDetailGraphTelemetry.vue'
import TaskDetailMetadataPanel from '@/components/task-detail/TaskDetailMetadataPanel.vue'
import TaskDetailWorkflowPresentation from '@/components/task-detail/TaskDetailWorkflowPresentation.vue'
import { canDelegateStandaloneTask } from '@/domain/task-detail/actions'
import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'
import {
  resolveTaskDetailProfile,
  usesWorkflowCapabilityLayout,
} from '@/domain/task-detail/profile'
import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'
import { resolveInstanceCapabilities } from '@/domain/task-detail/legacy-profile'
import {
  resolveTaskUserFacingStateForTask,
  TASK_USER_FACING_STATE_LABELS,
  userFacingStateTagType,
} from '@/domain/task-detail/user-state'
import { useAuthStore } from '@/stores/auth'
import type { Task, TaskCenterUserOption } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { isCaptureClosed, resolveAggregateMode } from '@/utils/workflowVideoSchema'
import { useTaskDetailActions } from '@/composables/useTaskDetailActions'
import { useTaskDetailCollaboration } from '@/composables/useTaskDetailCollaboration'
import { useTaskDetailData } from '@/composables/useTaskDetailData'

interface Props {
  initialSelectedTaskId?: string
  delegateUserOptions?: TaskCenterUserOption[]
  emptyDescription?: string
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
const watcherSubmitting = ref(false)
const watcherUserId = ref('')
const activityTimelineExpanded = ref<string[]>([])

const {
  loading,
  task,
  taskAttachments,
  taskActivity,
  taskWatchers,
  graphInstance,
  workflowRunEvents,
  departments,
  users,
  clearTaskDetails,
  loadReferenceData,
  loadSelectedTaskDetails,
} = useTaskDetailData({
  isManagementRole: () => authStore.isManagementRole,
  currentUser: () => authStore.user,
  onActivityLoadFailure: () => ElMessage.warning('活动时间线暂时无法加载'),
  onLoadFailure: (error) => ElMessage.error(getErrorMessage(error)),
})

const selectedTask = computed(() => task.value)

const {
  commentAttachmentResetKey,
  commentFiles,
  commentForm,
  commentSubmitting,
  handleCommentSubmit,
  handleTaskAttachmentUpload,
  selectedTaskFiles,
  taskAttachmentResetKey,
  taskAttachmentUploading,
} = useTaskDetailCollaboration({
  task,
  reloadTask: loadSelectedTaskDetails,
})

const {
  approvalSubmitting,
  closeCaptureSubmitting,
  delegateCandidateOptions,
  delegateDialogVisible,
  delegateForm,
  deliverableForm,
  deliverableReviewForm,
  deliverableSubmitting,
  extendDueDateDialogVisible,
  extendDueDateSubmitting,
  extendDueDateValue,
  handleAcceptAssignment,
  handleApprovalDecide,
  handleCloseCapture,
  handleDelegateAssignment,
  handleDeliverableReview,
  handleRejectAssignment,
  handleStatusTransition,
  handleSubmitDeliverable,
  handleTaskArchived,
  handshakeRejectDialogVisible,
  handshakeRejectReason,
  handshakeSubmitting,
  isStandaloneTask,
  nextStatusAction,
  openDelegateDialog,
  openExtendDueDateDialog,
  openHandshakeRejectDialog,
  openRejectDialog,
  openReworkDialog,
  rejectCommentDialogVisible,
  rejectCommentText,
  reloadAfterAction,
  reworkCommentText,
  reworkDialogVisible,
  statusSubmitting,
  submitExtendDueDate,
} = useTaskDetailActions({
  task,
  graphInstance,
  delegateUserOptions: () => props.delegateUserOptions,
  users,
  reloadTask: loadSelectedTaskDetails,
  onActionDone: () => emit('actionDone'),
})

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const userEmailMap = computed(() => new Map(users.value.map((user) => [user.id, user.email])))
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
const watcherOptions = computed(() =>
  users.value.filter(
    (user) =>
      user.status === 'active' &&
      !taskWatchers.value.some((watcher) => watcher.user_id === user.id),
  ),
)
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

const canDelegateTask = computed(() => {
  // Delegation is a Work Item assignment capability, driven by the backend
  // available_actions contract rather than by graph metadata.
  if (isStandaloneTask.value) {
    return canDelegateStandaloneTask(selectedTask.value)
  }
  return (
    canHandleHandshakeAction.value
    && currentHandshakeState.value !== 'rejected'
    && delegateCandidateOptions.value.length > 0
  )
})

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
const useWorkflowReviewMoreMenu = computed(
  () =>
    selectedTaskProfile.value.surface === 'review'
    && selectedTaskProfile.value.submitMode === 'review',
)
const canRejectProductionStep = computed(() => {
  const task = selectedTask.value
  const user = authStore.user
  if (!task || !user || !useWorkflowReviewMoreMenu.value || task.status !== 'review') {
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
const graphRunKind = computed(() => {
  const value = selectedTaskMetadata.value.run_kind
  return typeof value === 'string' ? value : ''
})
const isGraphCollectionRootTask = computed(
  () =>
    isGraphTemplateTask.value
    && selectedTaskMetadata.value.workflow_graph_root_task === true
    && selectedTaskProfile.value.features.tracking === true,
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
const usesWorkflowLayout = computed(() => usesWorkflowCapabilityLayout(selectedTaskProfile.value))
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
const instanceCapabilities = computed(() => {
  return resolveInstanceCapabilities(graphInstance.value?.context)
})
const showCloseCaptureButton = computed(
  () =>
    isGraphCollectionRootTask.value
    && instanceCapabilities.value.has('collection_finalize')
    && graphInstance.value !== null
    && batchAggregateMode.value === 'batch'
    && !captureClosed.value
    && canManageCaptureReject.value,
)
const showDetailHeaderActions = computed(() => {
  const surface = selectedTaskProfile.value.surface
  return surface !== 'structured_form'
    && surface !== 'collection'
    && surface !== 'run_overview'
})
const workflowPresentationRef = ref<InstanceType<typeof TaskDetailWorkflowPresentation> | null>(null)
const usesCompactDetailTelemetry = computed(() => TASK_CENTER_V2_UI_ENABLED)
const graphParentInstanceId = computed(() => {
  if (graphInstance.value?.parent_instance_id) {
    return graphInstance.value.parent_instance_id
  }
  const parentId = graphInstance.value?.context?.parent_instance_id
  return typeof parentId === 'string' ? parentId : null
})
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
  if (selectedTask.value?.assignee_id === userId && selectedTask.value.assignee_label) {
    return selectedTask.value.assignee_label
  }
  if (selectedTask.value?.creator_id === userId && selectedTask.value.creator_label) {
    return selectedTask.value.creator_label
  }
  return (
    delegateUserLabelMap.value.get(userId) ??
    userEmailMap.value.get(userId) ??
    `用户 ${userId.slice(0, 8)}`
  )
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

onMounted(() => {
  void loadReferenceData()
})

watch(
  () => props.initialSelectedTaskId,
  async (nextTaskId) => {
    if (!nextTaskId) {
      clearTaskDetails()
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
              :use-workflow-review-more-menu="useWorkflowReviewMoreMenu"
              :deliverable-review-comment="deliverableReviewForm.comment"
              :selected-task="selectedTask"
              :is-graph-handshake-task="isGraphHandshakeTask"
              :is-standalone-task="isStandaloneTask"
              :can-accept-task="canAcceptTask"
              :can-reject-task="canRejectTask"
              :can-delegate-task="canDelegateTask"
              :handshake-submitting="handshakeSubmitting"
              :next-status-action="nextStatusAction"
              :can-advance-selected-task-by-status="canAdvanceSelectedTaskByStatus"
              :status-submitting="statusSubmitting"
              :can-submit-deliverable="canSubmitDeliverable"
              :selected-task-profile="selectedTaskProfile"
              :workflow-deliverable-panel-ref="workflowPresentationRef"
              :deliverable-submitting="deliverableSubmitting"
              :uses-workflow-layout="usesWorkflowLayout"
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
              :resolve-department-name="resolveDepartmentName"
              :resolve-user-label="resolveUserLabel"
              :resolve-run-label="resolveTaskListRunLabel"
            />

            <TaskDetailWorkflowPresentation
              ref="workflowPresentationRef"
              :task="selectedTask"
              :graph-instance="graphInstance"
              :profile="selectedTaskProfile"
              :users="users"
              :can-manage-reject="canManageCaptureReject"
              :current-user-id="authStore.user?.id ?? null"
              :run-events="workflowRunEvents"
              :compact-telemetry="usesCompactDetailTelemetry"
              @reload="reloadAfterAction"
              @select-task="(taskId: string) => emit('selectTask', taskId)"
            />

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
              <el-form-item v-if="taskAttachments.length > 0" label="附件（可选，选择已有任务附件作为交付物）">
                <el-select
                  v-model="deliverableForm.attachment_ids"
                  multiple
                  filterable
                  clearable
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择附件"
                  data-testid="deliverable-attachment-select"
                >
                  <el-option
                    v-for="att in taskAttachments"
                    :key="att.id"
                    :label="att.original_filename"
                    :value="att.id"
                  />
                </el-select>
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

            <TaskDetailAttachmentsPanel
              v-if="!usesWorkflowLayout"
              :attachments="taskAttachments"
              :uploading="taskAttachmentUploading"
              :reset-key="taskAttachmentResetKey"
              @files-change="selectedTaskFiles = $event"
              @upload="handleTaskAttachmentUpload"
            />

            <TaskDetailCommentComposer
              v-model:content="commentForm.content"
              v-model:is-internal="commentForm.is_internal"
              :collapse="selectedTaskProfile.collapseComments"
              :is-management-role="authStore.isManagementRole"
              :submitting="commentSubmitting"
              :attachment-reset-key="commentAttachmentResetKey"
              @files-change="commentFiles = $event"
              @submit="handleCommentSubmit"
            />

            <template v-if="!selectedTaskProfile.collapseComments">

            <TaskDetailGraphTelemetry
              v-if="graphInstance && !usesWorkflowLayout"
              :graph-instance="graphInstance"
              :compact="usesCompactDetailTelemetry"
            />

            <TaskDetailContextPanel
              v-if="!usesWorkflowLayout"
              :task="selectedTask"
              :profile="selectedTaskProfile"
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
            />

            <el-collapse
              v-if="!usesWorkflowLayout"
              v-model="activityTimelineExpanded"
              class="page__activity-collapse"
              data-testid="task-detail-activity-collapse"
            >
              <el-collapse-item
                :title="`活动时间线${taskActivity.length > 0 ? `（${taskActivity.length}）` : ''}`"
                name="activity"
              >
                <TaskDetailActivityTimeline
                  :entries="taskActivity"
                  :resolve-user-label="resolveUserLabel"
                />
              </el-collapse-item>
            </el-collapse>

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

.page__activity-collapse {
  margin-top: 16px;
}

</style>
