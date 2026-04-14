import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  Department,
  Task,
  TaskActivityEntry,
  TaskStatsSummary,
  TaskWorkloadRow,
  User,
} from '@/types/api'

vi.mock('@/api/tasks', () => ({
  createTask: vi.fn(),
  createTaskComment: vi.fn(),
  getTaskStatsSummary: vi.fn(),
  getTaskWorkload: vi.fn(),
  listTaskActivity: vi.fn(),
  listTasks: vi.fn(),
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
  createTaskComment,
  getTaskStatsSummary,
  getTaskWorkload,
  listTaskActivity,
  listTasks,
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

describe('Tasks view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = mockUsers[0] ?? null

    vi.mocked(listTasks).mockResolvedValue(mockTasks)
    vi.mocked(listDepartments).mockResolvedValue([mockDepartment])
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.mocked(getTaskStatsSummary).mockResolvedValue(mockSummary)
    vi.mocked(getTaskWorkload).mockResolvedValue(mockWorkload)
    vi.mocked(listTaskActivity).mockResolvedValue(mockActivity)
    vi.mocked(listAttachments).mockResolvedValue([])
    vi.mocked(updateTaskStatus).mockResolvedValue({
      ...mockTasks[0],
      status: 'doing',
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

  it('renders summary cards and workload table', async () => {
    const wrapper = mount(TasksView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('任务总数')
    expect(wrapper.text()).toContain('负载概览')
    expect(wrapper.text()).toContain('研发部')
    expect(listTaskActivity).toHaveBeenCalledWith('task-1')
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
})
