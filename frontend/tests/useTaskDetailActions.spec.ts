import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/tasks', () => ({
  acceptTaskAssignment: vi.fn(),
  delegateTaskAssignment: vi.fn(),
  listTaskDelegateCandidates: vi.fn(),
  rejectTaskAssignment: vi.fn(),
  reviewTaskDeliverable: vi.fn(),
  submitTaskDeliverable: vi.fn(),
  updateTask: vi.fn(),
  updateTaskStatus: vi.fn(),
}))

vi.mock('@/api/workflow-graph', () => ({
  closeInstanceCapture: vi.fn(),
}))

import { ElMessage } from 'element-plus'
import {
  acceptTaskAssignment,
  delegateTaskAssignment,
  listTaskDelegateCandidates,
  reviewTaskDeliverable,
  updateTask,
  updateTaskStatus,
} from '@/api/tasks'
import { closeInstanceCapture } from '@/api/workflow-graph'
import { useTaskDetailActions } from '@/composables/useTaskDetailActions'
import type { Task, TaskCenterUserOption, User, WorkflowGraphInstanceDetail } from '@/types/api'

function taskFixture(overrides: Partial<Task> = {}): Task {
  return {
    id: 'task-1',
    title: '动作协调任务',
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'assignee-1',
    department_id: 'department-1',
    status: 'todo',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2026-08-11T00:00:00Z',
    updated_at: '2026-08-11T00:00:00Z',
    ...overrides,
  }
}

function setup(overrides: {
  task?: Task | null
  graphInstance?: WorkflowGraphInstanceDetail | null
  delegateUserOptions?: TaskCenterUserOption[]
  users?: User[]
} = {}) {
  const task = ref<Task | null>(overrides.task === undefined ? taskFixture() : overrides.task)
  const graphInstance = ref<WorkflowGraphInstanceDetail | null>(overrides.graphInstance ?? null)
  const delegateUserOptions = ref<TaskCenterUserOption[]>(overrides.delegateUserOptions ?? [])
  const users = ref<User[]>(overrides.users ?? [])
  const reloadTask = vi.fn().mockResolvedValue(true)
  const onActionDone = vi.fn()
  const actions = useTaskDetailActions({
    task,
    graphInstance,
    delegateUserOptions,
    users,
    reloadTask,
    onActionDone,
  })
  return { actions, graphInstance, onActionDone, reloadTask, task }
}

describe('useTaskDetailActions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(updateTaskStatus).mockResolvedValue(taskFixture({ status: 'doing' }))
    vi.mocked(reviewTaskDeliverable).mockResolvedValue(taskFixture({ status: 'done' }))
    vi.mocked(updateTask).mockResolvedValue(taskFixture())
    vi.mocked(closeInstanceCapture).mockResolvedValue({ message: '采集已关闭' } as never)
  })

  it('submits the next status and reloads the selected task once', async () => {
    const { actions, onActionDone, reloadTask } = setup()

    expect(actions.nextStatusAction.value?.status).toBe('doing')
    await actions.handleStatusTransition()

    expect(updateTaskStatus).toHaveBeenCalledWith('task-1', 'doing')
    expect(reloadTask).toHaveBeenCalledExactlyOnceWith('task-1')
    expect(onActionDone).toHaveBeenCalledOnce()
    expect(actions.statusSubmitting.value).toBe(false)
  })

  it('reviews a deliverable and resets approval form state', async () => {
    const { actions, reloadTask } = setup({ task: taskFixture({ status: 'review' }) })
    actions.deliverableReviewForm.comment = '达到验收标准'
    actions.deliverableReviewForm.quality_score = 4

    await actions.handleDeliverableReview('approve', actions.deliverableReviewForm.comment)

    expect(reviewTaskDeliverable).toHaveBeenCalledWith('task-1', {
      action: 'approve',
      comment: '达到验收标准',
      quality_score: 4,
    })
    expect(actions.deliverableReviewForm.comment).toBe('')
    expect(actions.deliverableReviewForm.quality_score).toBe(5)
    expect(reloadTask).toHaveBeenCalledWith('task-1')
  })

  it('requires an approval rejection reason before sending the command', async () => {
    const { actions, reloadTask } = setup({ task: taskFixture({ status: 'review' }) })
    actions.rejectCommentText.value = '   '

    await actions.handleApprovalDecide('rejected')

    expect(ElMessage.error).toHaveBeenCalledWith('驳回修改时必须填写原因')
    expect(reviewTaskDeliverable).not.toHaveBeenCalled()
    expect(reloadTask).not.toHaveBeenCalled()
  })

  it('loads standalone candidates and delegates to the first eligible user', async () => {
    vi.mocked(listTaskDelegateCandidates).mockResolvedValue([
      { user_id: 'assignee-1', display_name: '当前执行人', department_name: '研发部' },
      { user_id: 'assignee-2', display_name: '新执行人', department_name: '内容部' },
    ])
    vi.mocked(delegateTaskAssignment).mockResolvedValue(taskFixture({ assignee_id: 'assignee-2' }))
    const { actions, reloadTask } = setup({
      task: taskFixture({ execution_mode: 'standalone' }),
    })

    await actions.openDelegateDialog()

    expect(actions.delegateCandidateOptions.value.map((option) => option.user_id)).toEqual(['assignee-2'])
    expect(actions.delegateForm.assignee_id).toBe('assignee-2')
    actions.delegateForm.reason = '调整工作安排'
    await actions.handleDelegateAssignment()

    expect(delegateTaskAssignment).toHaveBeenCalledWith('task-1', {
      assignee_id: 'assignee-2',
      reason: '调整工作安排',
    })
    expect(reloadTask).toHaveBeenCalledWith('task-1')
    expect(actions.delegateDialogVisible.value).toBe(false)
  })

  it('resets handshake submitting and does not reload after a failed command', async () => {
    vi.mocked(acceptTaskAssignment).mockRejectedValue(new Error('accept failed'))
    const { actions, reloadTask } = setup()

    await actions.handleAcceptAssignment()

    expect(actions.handshakeSubmitting.value).toBe(false)
    expect(reloadTask).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('accept failed')
  })

  it('coordinates due-date extension and capture closure with the same refresh boundary', async () => {
    const graphInstance = { id: 'instance-1' } as WorkflowGraphInstanceDetail
    const { actions, reloadTask } = setup({ graphInstance })
    const nextDueDate = new Date('2026-08-20T08:00:00Z')
    actions.extendDueDateValue.value = nextDueDate

    await actions.submitExtendDueDate()
    await actions.handleCloseCapture()

    expect(updateTask).toHaveBeenCalledWith('task-1', { due_date: nextDueDate.toISOString() })
    expect(closeInstanceCapture).toHaveBeenCalledWith('instance-1')
    expect(reloadTask).toHaveBeenCalledTimes(2)
    expect(actions.extendDueDateSubmitting.value).toBe(false)
    expect(actions.closeCaptureSubmitting.value).toBe(false)
  })
})
