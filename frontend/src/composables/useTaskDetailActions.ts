import { computed, reactive, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { ElMessage } from 'element-plus'

import {
  reviewTaskDeliverable,
  submitTaskDeliverable,
  updateTask,
  updateTaskStatus,
} from '@/api/tasks'
import { closeInstanceCapture } from '@/api/workflow-graph'
import { resolveStatusLabel } from '@/components/task-detail/task-detail-labels'
import { useTaskAssignmentActions } from '@/composables/useTaskAssignmentActions'
import type {
  Task,
  TaskCenterUserOption,
  TaskStatus,
  User,
  WorkflowGraphInstanceDetail,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

type StatusAction = {
  label: string
  status: TaskStatus
  buttonType: 'primary' | 'warning' | 'success'
}

type TaskDetailActionOptions = {
  task: MaybeRefOrGetter<Task | null>
  graphInstance: MaybeRefOrGetter<WorkflowGraphInstanceDetail | null>
  delegateUserOptions: MaybeRefOrGetter<TaskCenterUserOption[]>
  users: MaybeRefOrGetter<User[]>
  reloadTask: (taskId: string) => Promise<unknown>
  onActionDone?: () => void
}

const NEXT_STATUS_ACTIONS: Record<Exclude<TaskStatus, 'done' | 'blocked'>, StatusAction> = {
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

export function useTaskDetailActions(options: TaskDetailActionOptions) {
  const deliverableSubmitting = ref(false)
  const statusSubmitting = ref(false)
  const approvalSubmitting = ref(false)
  const closeCaptureSubmitting = ref(false)
  const extendDueDateSubmitting = ref(false)

  const rejectCommentDialogVisible = ref(false)
  const rejectCommentText = ref('')
  const reworkDialogVisible = ref(false)
  const reworkCommentText = ref('')
  const extendDueDateDialogVisible = ref(false)
  const extendDueDateValue = ref<Date | null>(null)

  const deliverableForm = reactive({
    summary: '',
    attachment_ids: [] as string[],
  })

  const deliverableReviewForm = reactive({
    comment: '',
    quality_score: 5 as number | null,
  })

  const nextStatusAction = computed(() => {
    const task = toValue(options.task)
    if (!task || task.status === 'done' || task.status === 'blocked') {
      return null
    }
    return NEXT_STATUS_ACTIONS[task.status]
  })

  const assignmentActions = useTaskAssignmentActions({
    task: options.task,
    delegateUserOptions: options.delegateUserOptions,
    users: options.users,
    reloadAfterAction,
  })

  function resetDeliverableForm(): void {
    deliverableForm.summary = ''
    deliverableForm.attachment_ids = []
  }

  async function reloadAfterAction(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      options.onActionDone?.()
      return
    }
    await options.reloadTask(task.id)
    options.onActionDone?.()
  }

  function handleTaskArchived(): void {
    options.onActionDone?.()
  }

  function openExtendDueDateDialog(): void {
    const task = toValue(options.task)
    extendDueDateValue.value = task?.due_date ? new Date(task.due_date) : null
    extendDueDateDialogVisible.value = true
  }

  async function submitExtendDueDate(): Promise<void> {
    const task = toValue(options.task)
    if (!task || !extendDueDateValue.value) {
      ElMessage.warning('请选择新的截止时间')
      return
    }
    extendDueDateSubmitting.value = true
    try {
      await updateTask(task.id, { due_date: extendDueDateValue.value.toISOString() })
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
    const instanceId = toValue(options.graphInstance)?.id
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

  async function handleStatusTransition(): Promise<void> {
    const task = toValue(options.task)
    const statusAction = nextStatusAction.value
    if (!task || !statusAction) {
      return
    }

    statusSubmitting.value = true
    try {
      await updateTaskStatus(task.id, statusAction.status)
      ElMessage.success(`任务已更新为${resolveStatusLabel(statusAction.status)}`)
      await reloadAfterAction()
    } catch (error) {
      ElMessage.error(getErrorMessage(error))
    } finally {
      statusSubmitting.value = false
    }
  }

  async function handleSubmitDeliverable(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      ElMessage.warning('请先选择任务')
      return
    }
    if (!deliverableForm.summary.trim()) {
      ElMessage.warning('请填写交付说明')
      return
    }

    deliverableSubmitting.value = true
    try {
      await submitTaskDeliverable(task.id, {
        summary: deliverableForm.summary.trim(),
        attachment_ids: deliverableForm.attachment_ids,
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

  async function handleDeliverableReview(
    action: 'approve' | 'return_for_rework',
    comment?: string,
  ): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      return
    }

    approvalSubmitting.value = true
    try {
      await reviewTaskDeliverable(task.id, {
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

    const task = toValue(options.task)
    if (!task) {
      return
    }
    const comment = rejectCommentText.value.trim()
    if (!comment) {
      ElMessage.error('驳回修改时必须填写原因')
      return
    }

    approvalSubmitting.value = true
    try {
      await reviewTaskDeliverable(task.id, {
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

  function openReworkDialog(): void {
    reworkCommentText.value = ''
    reworkDialogVisible.value = true
  }

  return {
    approvalSubmitting,
    ...assignmentActions,
    closeCaptureSubmitting,
    deliverableForm,
    deliverableReviewForm,
    deliverableSubmitting,
    extendDueDateDialogVisible,
    extendDueDateSubmitting,
    extendDueDateValue,
    handleApprovalDecide,
    handleCloseCapture,
    handleDeliverableReview,
    handleStatusTransition,
    handleSubmitDeliverable,
    handleTaskArchived,
    nextStatusAction,
    openExtendDueDateDialog,
    openRejectDialog,
    openReworkDialog,
    rejectCommentDialogVisible,
    rejectCommentText,
    reloadAfterAction,
    reworkCommentText,
    reworkDialogVisible,
    statusSubmitting,
    submitExtendDueDate,
  }
}
