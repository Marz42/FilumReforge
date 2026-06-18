import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  Department,
  Task,
  TaskActivityEntry,
  TaskBoardColumn,
  TaskGanttEntry,
  TaskStatsSummary,
  TaskWatcher,
  TaskWorkloadRow,
  User,
} from '@/types/api'

vi.mock('@/api/tasks', () => ({
  acceptTaskAssignment: vi.fn(),
  addTaskWatchers: vi.fn(),
  createTask: vi.fn(),
  createTaskComment: vi.fn(),
  delegateTaskAssignment: vi.fn(),
  getTaskStatsSummary: vi.fn(),
  getTaskWorkload: vi.fn(),
  getTask: vi.fn(),
  listTaskActivity: vi.fn(),
  listTaskBoard: vi.fn(),
  listTaskGantt: vi.fn(),
  listTasks: vi.fn(),
  listTaskWatchers: vi.fn(),
  rejectTaskAssignment: vi.fn(),
  reviewTaskDeliverable: vi.fn(),
  submitTaskDeliverable: vi.fn(),
  updateTaskStatus: vi.fn(),
}))

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

vi.mock('@/api/attachments', () => ({
  listAttachments: vi.fn(),
  uploadAttachment: vi.fn(),
}))

import { listAttachments } from '@/api/attachments'
import { listDepartments } from '@/api/departments'
import {
  acceptTaskAssignment,
  createTaskComment,
  delegateTaskAssignment,
  getTaskStatsSummary,
  getTaskWorkload,
  getTask,
  listTaskActivity,
  listTaskBoard,
  listTaskGantt,
  listTasks,
  listTaskWatchers,
  rejectTaskAssignment,
  reviewTaskDeliverable,
  submitTaskDeliverable,
  updateTaskStatus,
} from '@/api/tasks'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import TasksView from '@/views/TasksView.vue'

const mockDepartment: Department = {
  id: 'dept-1',
  name: '研发部',
  code: 'engineering',
  parent_id: null,
  manager_id: 'user-1',
  sort_order: 1,
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockUsers: User[] = [
  {
    id: 'user-1',
    email: 'admin@example.com',
    role: 'admin',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-2',
    email: 'employee@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-3',
    email: 'watcher@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
]

const mockTasks: Task[] = [
  {
    id: 'task-1',
    title: '推进评论流',
    description: '补齐前后端协同链路',
    creator_id: 'user-1',
    assignee_id: 'user-2',
    department_id: 'dept-1',
    status: 'todo',
    priority: 'high',
    due_date: '2025-01-03T10:00:00Z',
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {},
    created_at: '2025-01-02T09:00:00Z',
    updated_at: '2025-01-02T09:00:00Z',
  },
]

const mockBoard: TaskBoardColumn[] = [
  {
    status: 'todo',
    tasks: mockTasks,
  },
  {
    status: 'doing',
    tasks: [],
  },
  {
    status: 'review',
    tasks: [],
  },
  {
    status: 'done',
    tasks: [],
  },
]

const mockGantt: TaskGanttEntry[] = [
  {
    task: mockTasks[0]!,
    dependency_ids: ['task-0'],
  },
]

const mockWatchers: TaskWatcher[] = [
  {
    id: 'watcher-1',
    task_id: 'task-1',
    user_id: 'user-3',
    relation: 'watcher',
    created_by: 'user-1',
    created_at: '2025-01-02T09:05:00Z',
  },
]

const mockSummary: TaskStatsSummary = {
  total_tasks: 2,
  completed_tasks: 1,
  completion_rate: 0.5,
  overdue_tasks: 1,
  overdue_rate: 0.5,
  tasks_by_status: {
    todo: 1,
    doing: 0,
    review: 0,
    done: 1,
  },
}

const mockWorkload: TaskWorkloadRow[] = [
  {
    assignee_id: 'user-2',
    assignee_email: 'employee@example.com',
    assignee_label: '员工（employee@example.com）',
    department_id: 'dept-1',
    department_name: '研发部',
    total_tasks: 2,
    open_tasks: 1,
    completed_tasks: 1,
    overdue_tasks: 1,
  },
]

const mockActivity: TaskActivityEntry[] = [
  {
    entry_type: 'log',
    created_at: '2025-01-02T09:30:00Z',
    comment: null,
    log: {
      id: 'log-1',
      task_id: 'task-1',
      operator_id: 'user-1',
      action_type: 'created',
      from_status: null,
      to_status: null,
      detail: {},
      created_at: '2025-01-02T09:30:00Z',
    },
  },
]

function mockTaskList(tasks: Task[]): void {
  vi.mocked(listTasks).mockResolvedValue(tasks)
  vi.mocked(getTask).mockImplementation(async (taskId: string) => {
    const task = tasks.find((item) => item.id === taskId)
    if (!task) {
      throw new Error(`Task ${taskId} not found`)
    }
    return task
  })
}

describe('Tasks view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.user = mockUsers[0] ?? null

    mockTaskList(mockTasks)
    vi.mocked(listTaskBoard).mockResolvedValue(mockBoard)
    vi.mocked(listTaskGantt).mockResolvedValue(mockGantt)
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.mocked(getTaskStatsSummary).mockResolvedValue(mockSummary)
    vi.mocked(getTaskWorkload).mockResolvedValue(mockWorkload)
    vi.mocked(listTaskActivity).mockResolvedValue(mockActivity)
    vi.mocked(listTaskWatchers).mockResolvedValue(mockWatchers)
    vi.mocked(listAttachments).mockResolvedValue([])
    vi.mocked(updateTaskStatus).mockResolvedValue({
      ...mockTasks[0],
      status: 'doing',
    })
    vi.mocked(acceptTaskAssignment).mockResolvedValue({
      ...mockTasks[0],
      extra_metadata: {
        workflow_graph_instance_id: 'graph-1',
        workflow_node_instance_id: 'node-1',
        workflow_handshake_state: 'accepted',
      },
    })
    vi.mocked(rejectTaskAssignment).mockResolvedValue({
      ...mockTasks[0],
      extra_metadata: {
        workflow_graph_instance_id: 'graph-1',
        workflow_node_instance_id: 'node-1',
        workflow_handshake_state: 'rejected',
        latest_reject_reason: '目标需要再明确',
      },
    })
    vi.mocked(delegateTaskAssignment).mockResolvedValue({
      ...mockTasks[0],
      assignee_id: 'user-3',
      extra_metadata: {
        workflow_graph_instance_id: 'graph-1',
        workflow_node_instance_id: 'node-1',
        workflow_handshake_state: 'assigned',
        latest_delegate_reason: '请更熟悉客户的人继续处理',
      },
    })
    vi.mocked(submitTaskDeliverable).mockResolvedValue({
      ...mockTasks[0],
      status: 'review',
      extra_metadata: {
        latest_deliverable_summary: '已完成第一版交付',
      },
    })
    vi.mocked(reviewTaskDeliverable).mockResolvedValue({
      ...mockTasks[0],
      status: 'done',
      completed_at: '2025-01-02T11:00:00Z',
      extra_metadata: {
        latest_review_state: 'approved',
        latest_review_quality_score: 5,
      },
    })
    vi.mocked(createTaskComment).mockResolvedValue({
      id: 'comment-1',
      task_id: 'task-1',
      user_id: 'user-1',
      content: '请补充评审结论。',
      content_format: 'markdown',
      is_internal: true,
      created_at: '2025-01-02T10:00:00Z',
      updated_at: '2025-01-02T10:00:00Z',
      attachments: [],
    })
  })

  it('renders summary cards and watcher details', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('任务总数')
    expect(wrapper.text()).toContain('负载概览')
    expect(wrapper.text()).toContain('研发部')
    expect(wrapper.text()).toContain('watcher@example.com')
    expect(listTaskActivity).toHaveBeenCalledWith('task-1')
    expect(listTaskWatchers).toHaveBeenCalledWith('task-1')
  })

  it('submits status transition and comment actions', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const statusButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('开始处理'))
    expect(statusButton).toBeTruthy()
    await statusButton?.trigger('click')
    await flushPromises()

    expect(updateTaskStatus).toHaveBeenCalledWith('task-1', 'doing')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('请补充评审结论。')
    const commentButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('提交评论'))
    expect(commentButton).toBeTruthy()
    await commentButton?.trigger('click')
    await flushPromises()

    expect(createTaskComment).toHaveBeenCalledWith('task-1', {
      content: '请补充评审结论。',
      is_internal: false,
      files: [],
    })
  })

  it('switches between list, board, and gantt views', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const boardButton = wrapper.findAll('button').find((node) => node.text().includes('看板'))
    expect(boardButton).toBeTruthy()
    await boardButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('推进评论流')
    expect(wrapper.text()).toContain('待办')

    const ganttButton = wrapper.findAll('button').find((node) => node.text().includes('甘特'))
    expect(ganttButton).toBeTruthy()
    await ganttButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('task-0')
  })

  it('hides the standalone task composer when embedded in task center tracking', async () => {
    const wrapper = mount(TasksView, {
      props: {
        showCreateTaskComposer: false,
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).not.toContain('新建任务')
  })

  it('shows deliverable review actions instead of generic review completion for manual review tasks', async () => {
    mockTaskList([
      {
        ...mockTasks[0],
        status: 'review',
        extra_metadata: {
          latest_deliverable_summary: '已完成第一版交付',
        },
      },
    ])

    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('验收通过')
    expect(wrapper.text()).toContain('打回返工')
    expect(wrapper.text()).toContain('完成质量评分')
    expect(wrapper.text()).not.toContain('标记完成')

    const approveButton = wrapper.findAll('button').find((button) => button.text().includes('验收通过'))
    expect(approveButton).toBeTruthy()
    await approveButton?.trigger('click')
    await flushPromises()

    expect(reviewTaskDeliverable).toHaveBeenCalledWith('task-1', {
      action: 'approve',
      comment: null,
      quality_score: 5,
    })
  })

  it('shows handshake actions for assigned graph manual tasks and accepts assignment', async () => {
    mockTaskList([
      {
        ...mockTasks[0],
        extra_metadata: {
          workflow_graph_instance_id: 'graph-1',
          workflow_node_instance_id: 'node-1',
          workflow_handshake_state: 'assigned',
        },
      },
    ])

    const wrapper = mount(TasksView, {
      props: {
        delegateUserOptions: [
          {
            user_id: 'user-3',
            email: 'watcher@example.com',
            real_name: null,
            department_id: 'dept-1',
            department_name: '研发部',
            label: 'watcher@example.com',
          },
        ],
      },
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('接受任务')
    expect(wrapper.text()).toContain('退回协商')
    expect(wrapper.text()).toContain('转办')
    expect(wrapper.text()).not.toContain('开始处理')

    const acceptButton = wrapper.findAll('button').find((button) => button.text().includes('接受任务'))
    expect(acceptButton).toBeTruthy()
    await acceptButton?.trigger('click')
    await flushPromises()

    expect(acceptTaskAssignment).toHaveBeenCalledWith('task-1')
  })

  it('shows start action after graph manual task has been accepted', async () => {
    mockTaskList([
      {
        ...mockTasks[0],
        extra_metadata: {
          workflow_graph_instance_id: 'graph-1',
          workflow_node_instance_id: 'node-1',
          workflow_handshake_state: 'accepted',
        },
      },
    ])

    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('开始处理')
    expect(wrapper.text()).not.toContain('接受任务')
  })

  it('shows iteration version badge and deep rejection reason for replayed graph tasks', async () => {
    mockTaskList([
      {
        ...mockTasks[0],
        extra_metadata: {
          workflow_graph_instance_id: 'graph-1',
          workflow_node_instance_id: 'node-2',
          workflow_node_iteration: 2,
          workflow_deep_rejection_reason: '需要重新评估方案',
          workflow_handshake_state: 'accepted',
        },
      },
    ])

    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('V2')
    expect(wrapper.text()).toContain('系统深度打回重放')
    expect(wrapper.text()).toContain('需要重新评估方案')
  })

  it('does not show iteration badge for first-iteration graph tasks', async () => {
    mockTaskList([
      {
        ...mockTasks[0],
        extra_metadata: {
          workflow_graph_instance_id: 'graph-1',
          workflow_node_instance_id: 'node-1',
          workflow_node_iteration: 1,
          workflow_handshake_state: 'accepted',
        },
      },
    ])

    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).not.toContain('系统深度打回重放')
  })
})
