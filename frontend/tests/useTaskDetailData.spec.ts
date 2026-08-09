import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/attachments', () => ({
  listAttachments: vi.fn(),
}))
vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))
vi.mock('@/api/tasks', () => ({
  getTask: vi.fn(),
  listTaskActivity: vi.fn(),
  listTaskWatchers: vi.fn(),
}))
vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))
vi.mock('@/api/workflow-graph', () => ({
  getWorkflowGraphInstance: vi.fn(),
  listInstanceEvents: vi.fn(),
}))

import { listAttachments } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import { getTask, listTaskActivity, listTaskWatchers } from '@/api/tasks'
import { listUsers } from '@/api/users'
import { getWorkflowGraphInstance, listInstanceEvents } from '@/api/workflow-graph'
import { useTaskDetailData } from '@/composables/useTaskDetailData'
import type { Task, User } from '@/types/api'

function taskFixture(id: string, instanceId?: string): Task {
  return {
    id,
    title: `任务 ${id}`,
    description: null,
    creator_id: 'creator-1',
    assignee_id: 'assignee-1',
    department_id: 'department-1',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: instanceId ? { workflow_graph_instance_id: instanceId } : {},
    created_at: '2026-08-10T00:00:00Z',
    updated_at: '2026-08-10T00:00:00Z',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => {
    resolve = next
  })
  return { promise, resolve }
}

describe('useTaskDetailData', () => {
  const currentUser = ref<User | null>({
    id: 'user-1',
    email: 'employee@example.com',
    role: 'employee',
    status: 'active',
    created_at: '2026-08-10T00:00:00Z',
  })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listAttachments).mockResolvedValue([])
    vi.mocked(listTaskActivity).mockResolvedValue([])
    vi.mocked(listTaskWatchers).mockResolvedValue([])
    vi.mocked(listDepartments).mockResolvedValue([])
    vi.mocked(listUsers).mockResolvedValue([])
  })

  it('loads one coherent task, related collections and graph snapshot', async () => {
    const loadedTask = taskFixture('task-1', 'instance-1')
    vi.mocked(getTask).mockResolvedValue(loadedTask)
    vi.mocked(listAttachments).mockResolvedValue([{ id: 'attachment-1' }] as never)
    vi.mocked(listTaskActivity).mockResolvedValue([{ id: 'activity-1' }] as never)
    vi.mocked(listTaskWatchers).mockResolvedValue([{ user_id: 'watcher-1' }] as never)
    vi.mocked(getWorkflowGraphInstance).mockResolvedValue({ id: 'instance-1' } as never)
    vi.mocked(listInstanceEvents).mockResolvedValue({
      items: [{ id: 'event-1' }],
      next_cursor: null,
    } as never)

    const data = useTaskDetailData({
      isManagementRole: false,
      currentUser,
    })
    const loaded = await data.loadSelectedTaskDetails('task-1')

    expect(loaded).toBe(true)
    expect(getTask).toHaveBeenCalledOnce()
    expect(data.task.value).toStrictEqual(loadedTask)
    expect(data.taskAttachments.value).toHaveLength(1)
    expect(data.taskActivity.value).toHaveLength(1)
    expect(data.taskWatchers.value).toHaveLength(1)
    expect(data.graphInstance.value?.id).toBe('instance-1')
    expect(data.workflowRunEvents.value).toHaveLength(1)
    expect(data.loading.value).toBe(false)
  })

  it('keeps the newest selection when an older request resolves later', async () => {
    const first = deferred<Task>()
    const second = deferred<Task>()
    vi.mocked(getTask).mockImplementation((taskId) => {
      return taskId === 'task-1' ? first.promise : second.promise
    })
    const data = useTaskDetailData({
      isManagementRole: false,
      currentUser,
    })

    const firstLoad = data.loadSelectedTaskDetails('task-1')
    const secondLoad = data.loadSelectedTaskDetails('task-2')
    second.resolve(taskFixture('task-2'))
    await secondLoad
    first.resolve(taskFixture('task-1'))
    await firstLoad

    expect(data.task.value?.id).toBe('task-2')
    expect(listTaskActivity).toHaveBeenCalledTimes(1)
    expect(listTaskActivity).toHaveBeenCalledWith('task-2')
  })

  it('degrades optional collections independently and reports timeline failure once', async () => {
    vi.mocked(getTask).mockResolvedValue(taskFixture('task-1', 'instance-1'))
    vi.mocked(listAttachments).mockRejectedValue(new Error('attachment unavailable'))
    vi.mocked(listTaskActivity).mockRejectedValue(new Error('activity unavailable'))
    vi.mocked(listTaskWatchers).mockRejectedValue(new Error('watchers unavailable'))
    vi.mocked(getWorkflowGraphInstance).mockRejectedValue(new Error('graph unavailable'))
    const onActivityLoadFailure = vi.fn()
    const data = useTaskDetailData({
      isManagementRole: false,
      currentUser,
      onActivityLoadFailure,
    })

    expect(await data.loadSelectedTaskDetails('task-1')).toBe(true)
    expect(data.task.value?.id).toBe('task-1')
    expect(data.taskAttachments.value).toEqual([])
    expect(data.taskActivity.value).toEqual([])
    expect(data.taskWatchers.value).toEqual([])
    expect(data.graphInstance.value).toBeNull()
    expect(data.workflowRunEvents.value).toEqual([])
    expect(onActivityLoadFailure).toHaveBeenCalledOnce()
  })

  it('clears the previous detail and reports a primary task load failure', async () => {
    vi.mocked(getTask)
      .mockResolvedValueOnce(taskFixture('task-1'))
      .mockRejectedValueOnce(new Error('task unavailable'))
    const onLoadFailure = vi.fn()
    const data = useTaskDetailData({
      isManagementRole: false,
      currentUser,
      onLoadFailure,
    })

    expect(await data.loadSelectedTaskDetails('task-1')).toBe(true)
    expect(data.task.value?.id).toBe('task-1')
    expect(await data.loadSelectedTaskDetails('task-2')).toBe(false)
    expect(data.task.value).toBeNull()
    expect(onLoadFailure).toHaveBeenCalledOnce()
  })

  it('loads all users for managers and only the current user for employees', async () => {
    const managerMode = ref(true)
    const manager = { ...currentUser.value!, role: 'admin' as const }
    vi.mocked(listUsers).mockResolvedValue([manager])
    const data = useTaskDetailData({
      isManagementRole: managerMode,
      currentUser,
    })

    await data.loadReferenceData()
    expect(data.users.value).toEqual([manager])
    expect(listUsers).toHaveBeenCalledOnce()

    managerMode.value = false
    await data.loadReferenceData()
    expect(data.users.value).toEqual([currentUser.value])
    expect(listUsers).toHaveBeenCalledOnce()
  })
})
