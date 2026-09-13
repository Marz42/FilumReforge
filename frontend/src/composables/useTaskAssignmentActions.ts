import { computed, reactive, ref, toValue, type MaybeRefOrGetter } from 'vue'
import { ElMessage } from 'element-plus'

import {
  acceptTaskAssignment,
  delegateTaskAssignment,
  listTaskDelegateCandidates,
  rejectTaskAssignment,
} from '@/api/tasks'
import { isStandaloneTask as isStandaloneTaskRecord } from '@/domain/task-detail/actions'
import type { Task, TaskCenterUserOption, User } from '@/types/api'
import { showError } from '@/utils/errors'

type TaskAssignmentActionOptions = {
  task: MaybeRefOrGetter<Task | null>
  delegateUserOptions: MaybeRefOrGetter<TaskCenterUserOption[]>
  users: MaybeRefOrGetter<User[]>
  reloadAfterAction: () => Promise<void>
}

export function useTaskAssignmentActions(options: TaskAssignmentActionOptions) {
  const handshakeSubmitting = ref(false)
  const handshakeRejectDialogVisible = ref(false)
  const handshakeRejectReason = ref('')
  const delegateDialogVisible = ref(false)
  const delegateForm = reactive({ assignee_id: '', reason: '' })
  const standaloneDelegateCandidates = ref<TaskCenterUserOption[]>([])

  const isStandaloneTask = computed(() => isStandaloneTaskRecord(toValue(options.task)))

  const delegateCandidateOptions = computed(() => {
    const currentAssigneeId = toValue(options.task)?.assignee_id ?? ''
    if (isStandaloneTask.value) {
      return standaloneDelegateCandidates.value.filter(
        (option) => option.user_id !== currentAssigneeId,
      )
    }

    const providedOptions = toValue(options.delegateUserOptions)
    if (providedOptions.length > 0) {
      return providedOptions.filter((option) => option.user_id !== currentAssigneeId)
    }

    return toValue(options.users)
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

  function openHandshakeRejectDialog(): void {
    handshakeRejectReason.value = ''
    handshakeRejectDialogVisible.value = true
  }

  async function openDelegateDialog(): Promise<void> {
    const task = toValue(options.task)
    if (isStandaloneTask.value && task) {
      try {
        const candidates = await listTaskDelegateCandidates(task.id)
        standaloneDelegateCandidates.value = candidates.map((candidate) => ({
          user_id: candidate.user_id,
          email: '',
          real_name: candidate.display_name,
          department_id: null,
          department_name: candidate.department_name,
          label: candidate.department_name
            ? `${candidate.display_name}（${candidate.department_name}）`
            : candidate.display_name,
        }))
      } catch (error) {
        showError(error)
        standaloneDelegateCandidates.value = []
      }
    }
    delegateForm.assignee_id = delegateCandidateOptions.value[0]?.user_id ?? ''
    delegateForm.reason = ''
    delegateDialogVisible.value = true
  }

  async function handleAcceptAssignment(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      return
    }

    handshakeSubmitting.value = true
    try {
      await acceptTaskAssignment(task.id)
      ElMessage.success('任务已接受，可以开始处理')
      await options.reloadAfterAction()
    } catch (error) {
      showError(error)
    } finally {
      handshakeSubmitting.value = false
    }
  }

  async function handleRejectAssignment(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
      return
    }
    if (!handshakeRejectReason.value.trim()) {
      ElMessage.warning('请填写退回协商原因')
      return
    }

    handshakeSubmitting.value = true
    try {
      await rejectTaskAssignment(task.id, {
        reason: handshakeRejectReason.value.trim(),
      })
      ElMessage.success('任务已退回协商')
      handshakeRejectDialogVisible.value = false
      handshakeRejectReason.value = ''
      await options.reloadAfterAction()
    } catch (error) {
      showError(error)
    } finally {
      handshakeSubmitting.value = false
    }
  }

  async function handleDelegateAssignment(): Promise<void> {
    const task = toValue(options.task)
    if (!task) {
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
      await delegateTaskAssignment(task.id, {
        assignee_id: delegateForm.assignee_id,
        reason: delegateForm.reason.trim(),
      })
      ElMessage.success(
        isStandaloneTask.value ? '任务已转办给新的执行人' : '任务已转办，等待新执行人确认',
      )
      delegateDialogVisible.value = false
      delegateForm.assignee_id = ''
      delegateForm.reason = ''
      await options.reloadAfterAction()
    } catch (error) {
      showError(error)
    } finally {
      handshakeSubmitting.value = false
    }
  }

  return {
    delegateCandidateOptions,
    delegateDialogVisible,
    delegateForm,
    handleAcceptAssignment,
    handleDelegateAssignment,
    handleRejectAssignment,
    handshakeRejectDialogVisible,
    handshakeRejectReason,
    handshakeSubmitting,
    isStandaloneTask,
    openDelegateDialog,
    openHandshakeRejectDialog,
  }
}
