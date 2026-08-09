import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/attachments', () => ({
  listAttachments: vi.fn(),
  uploadAttachment: vi.fn(),
}))
vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))
vi.mock('@/api/tasks', () => ({
  acceptTaskAssignment: vi.fn(),
  addTaskWatchers: vi.fn(),
  createTaskComment: vi.fn(),
  delegateTaskAssignment: vi.fn(),
  getTask: vi.fn(),
  listTaskActivity: vi.fn(),
  listTaskDelegateCandidates: vi.fn(),
  listTaskWatchers: vi.fn(),
  rejectTaskAssignment: vi.fn(),
  reviewTaskDeliverable: vi.fn(),
  submitTaskDeliverable: vi.fn(),
  updateTask: vi.fn(),
  updateTaskStatus: vi.fn(),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))
vi.mock('@/api/workflow-graph', () => ({
  closeInstanceCapture: vi.fn(),
  getWorkflowGraphInstance: vi.fn(),
  listInstanceEvents: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isManagementRole: false,
    user: {
      id: 'user-1',
      email: 'employee@example.com',
      role: 'employee',
      status: 'active',
      created_at: '2026-08-10T00:00:00Z',
    },
  }),
}))

import { listAttachments } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import { getTask, listTaskActivity, listTaskWatchers } from '@/api/tasks'
import TaskDetailShell from '@/components/task-detail/TaskDetailShell.vue'
import type { Task } from '@/types/api'

function taskFixture(id: string): Task {
  return {
    id,
    title: `任务 ${id}`,
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'user-1',
    department_id: 'department-1',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2026-08-10T00:00:00Z',
    updated_at: '2026-08-10T00:00:00Z',
  }
}

describe('TaskDetailShell data coordination', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getTask).mockImplementation(async (taskId) => taskFixture(taskId))
    vi.mocked(listAttachments).mockResolvedValue([])
    vi.mocked(listTaskActivity).mockResolvedValue([])
    vi.mocked(listTaskWatchers).mockResolvedValue([])
    vi.mocked(listDepartments).mockResolvedValue([])
  })

  it('loads the initial task once and refreshes once when selection changes', async () => {
    const wrapper = shallowMount(TaskDetailShell, {
      props: { initialSelectedTaskId: 'task-1' },
      global: {
        directives: { loading: () => undefined },
      },
    })
    await flushPromises()

    expect(getTask).toHaveBeenCalledTimes(1)
    expect(getTask).toHaveBeenLastCalledWith('task-1')

    await wrapper.setProps({ initialSelectedTaskId: 'task-2' })
    await flushPromises()

    expect(getTask).toHaveBeenCalledTimes(2)
    expect(getTask).toHaveBeenLastCalledWith('task-2')
  })
})
