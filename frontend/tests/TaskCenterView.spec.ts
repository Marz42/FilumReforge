import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Task, TaskCenterSnapshot, User } from '@/types/api'

vi.mock('@/api/task-center', () => ({
  getTaskCenterSnapshot: vi.fn(),
}))

vi.mock('@/api/attachments', () => ({
  uploadAttachment: vi.fn(),
  listAttachments: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/tasks', () => ({
  createTask: vi.fn(),
  createTaskComment: vi.fn(),
  searchTasks: vi.fn(),
  listTasks: vi.fn(),
  listTasksByIds: vi.fn(),
  getTask: vi.fn(),
  listTaskActivity: vi.fn().mockResolvedValue([]),
  listTaskWatchers: vi.fn().mockResolvedValue([]),
}))

const route = reactive({
  query: {} as Record<string, string | undefined>,
})
const replace = vi.fn(async ({ query }: { query?: Record<string, string> }) => {
  route.query = query ?? {}
})

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({
    replace,
    push: vi.fn(),
  }),
}))

import { getTaskCenterSnapshot } from '@/api/task-center'
import { createTask, createTaskComment, getTask, listTasksByIds } from '@/api/tasks'
import { useAuthStore } from '@/stores/auth'
import TaskCenterView from '@/views/TaskCenterView.vue'

const mockUser: User = {
  id: 'user-1',
  email: 'employee@example.com',
  role: 'employee',
  status: 'active',
  last_login_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockSnapshot: TaskCenterSnapshot = {
  permissions: {
    can_manage_templates: false,
    can_publish_task: true,
  },
  template_summaries: [],
  publish_department_options: [{ id: 'dept-1', label: '内容部' }],
  publish_user_options: [
    {
      user_id: 'user-1',
      email: 'employee@example.com',
      real_name: '内容成员',
      department_id: 'dept-1',
      department_name: '内容部',
      label: '内容成员（employee@example.com）',
    },
  ],
  task_inbox: [
    {
      task_id: 'task-1',
      title: '整理四月周报',
      priority: 'high',
      status: 'todo',
      due_date: '2025-01-03T10:00:00Z',
      department_name: '内容部',
      current_stage_label: '待处理',
      current_handler_label: '内容成员',
    },
  ],
  task_tracking: [
    {
      task_id: 'task-2',
      title: '跟进视频发布',
      priority: 'medium',
      status: 'doing',
      due_date: '2025-01-04T12:00:00Z',
      department_name: '内容部',
      relation_types: ['执行'],
      current_stage_label: '制作中',
      current_handler_label: '内容成员',
      latest_deliverable_submitted_at: '2025-01-04T08:00:00Z',
      rework_count: 1,
      review_quality_score: 4,
      is_pending_review: true,
    },
    {
      task_id: 'task-overdue',
      title: '逾期任务示例',
      priority: 'high',
      status: 'doing',
      due_date: '2020-01-01T00:00:00Z',
      department_name: '内容部',
      relation_types: ['执行'],
      current_stage_label: '进行中',
      current_handler_label: '内容成员',
      latest_deliverable_submitted_at: null,
      rework_count: 0,
      review_quality_score: null,
      is_pending_review: false,
    },
  ],
  task_history: [
    {
      task_id: 'task-3',
      title: '归档旧公告',
      priority: 'low',
      due_date: '2025-01-02T10:00:00Z',
      completed_at: '2025-01-02T09:30:00Z',
      department_name: '内容部',
      relation_types: ['执行'],
      source_type: 'manual',
    },
  ],
  task_memos: [],
}

const detailShellStub = {
  props: ['initialSelectedTaskId'],
  template: '<div data-testid="tasks-detail-stub">{{ initialSelectedTaskId || "empty" }}</div>',
}

const detailShellSimpleStub = {
  template: '<div data-testid="tasks-detail-stub">detail</div>',
}

function buildTasksFromSnapshot(snapshot: TaskCenterSnapshot): Task[] {
  const tasks: Task[] = []

  for (const item of snapshot.task_inbox) {
    tasks.push({
      id: item.task_id,
      title: item.title,
      description: null,
      creator_id: 'user-1',
      assignee_id: 'user-1',
      department_id: 'dept-1',
      status: item.status,
      priority: item.priority,
      due_date: item.due_date,
      started_at: null,
      completed_at: null,
      parent_task_id: null,
      source_type: 'manual',
      extra_metadata: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })
  }

  for (const item of snapshot.task_tracking) {
    tasks.push({
      id: item.task_id,
      title: item.title,
      description: null,
      creator_id: 'user-1',
      assignee_id: 'user-1',
      department_id: 'dept-1',
      status: item.status,
      priority: item.priority,
      due_date: item.due_date,
      started_at: null,
      completed_at: null,
      parent_task_id: null,
      source_type: 'manual',
      extra_metadata: {
        latest_deliverable_submitted_at: item.latest_deliverable_submitted_at,
        rework_count: item.rework_count,
        latest_review_quality_score: item.review_quality_score,
      },
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })
  }

  for (const item of snapshot.task_history) {
    tasks.push({
      id: item.task_id,
      title: item.title,
      description: null,
      creator_id: 'user-1',
      assignee_id: 'user-1',
      department_id: 'dept-1',
      status: 'done',
      priority: item.priority,
      due_date: item.due_date,
      started_at: null,
      completed_at: item.completed_at,
      parent_task_id: null,
      source_type: item.source_type,
      extra_metadata: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })
  }

  return tasks
}

function syncListTasksFromSnapshot(snapshot: TaskCenterSnapshot): void {
  const tasks = buildTasksFromSnapshot(snapshot)
  vi.mocked(listTasksByIds).mockImplementation(async (ids: string[]) =>
    ids
      .map((id) => tasks.find((item) => item.id === id))
      .filter((task): task is Task => task !== undefined),
  )
  vi.mocked(getTask).mockImplementation(async (taskId: string) => {
    const task = tasks.find((item) => item.id === taskId)
    if (!task) {
      throw new Error(`Task ${taskId} not found`)
    }
    return task
  })
}

describe('TaskCenter view', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    route.query = {}

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.user = mockUser

    vi.mocked(getTaskCenterSnapshot).mockResolvedValue(mockSnapshot)
    syncListTasksFromSnapshot(mockSnapshot)
  })

  it('renders inbox by default with filter chips and master-detail layout', async () => {
    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: detailShellSimpleStub,
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-create-task"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-filter-cards"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-filter-inbox"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-inbox-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('整理四月周报')
    expect(wrapper.find('[data-testid="tasks-detail-stub"]').exists()).toBe(true)
  })

  it('renders stable selectors for the task creation dialog', async () => {
    const wrapper = mount(TaskCenterView, {
      attachTo: document.body,
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    await wrapper.find('[data-testid="task-center-create-task"]').trigger('click')
    await flushPromises()

    expect(document.querySelector('[data-testid="task-center-task-dialog"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="task-center-task-title"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="task-center-task-department"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="task-center-task-assignee"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="task-center-task-attachments"]')).not.toBeNull()
    expect(document.querySelector('[data-testid="task-center-task-submit"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('maps legacy tasks tab to tracking filter', async () => {
    route.query = { tab: 'tasks' }

    mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    expect(replace).toHaveBeenCalledWith({
      name: 'task-center',
      query: {
        filter: 'tracking',
      },
    })
  })

  it('updates route when filter chip changes', async () => {
    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    await wrapper.find('[data-testid="task-filter-tracking"]').trigger('click')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith({
      name: 'task-center',
      query: {
        filter: 'tracking',
      },
    })
  })

  it('shows tracking data in master list when filter is tracking', async () => {
    route.query = { filter: 'tracking' }

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-tracking-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('跟进视频发布')
    expect(wrapper.text()).toContain('进行中')
    expect(wrapper.text()).not.toContain('归档旧公告')
  })

  it('shows overdue tag for tasks past due date in tracking filter', async () => {
    route.query = { filter: 'tracking' }

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('逾期任务示例')
    expect(wrapper.text()).toContain('已逾期')
  })

  it('does not rewrite selected query outside search mode when inbox is empty', async () => {
    const emptySnapshot = {
      ...mockSnapshot,
      task_inbox: [],
      task_tracking: [],
      task_history: [],
    }
    vi.mocked(getTaskCenterSnapshot).mockResolvedValue(emptySnapshot)
    syncListTasksFromSnapshot(emptySnapshot)
    route.query = { filter: 'inbox', selected: 'missing-task' }

    mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: detailShellStub,
        },
      },
    })

    await flushPromises()

    expect(replace).not.toHaveBeenCalled()
  })

  it('does not pass selected id to detail when master list is empty', async () => {
    const emptySnapshot = {
      ...mockSnapshot,
      task_inbox: [],
      task_tracking: [],
      task_history: [],
    }
    vi.mocked(getTaskCenterSnapshot).mockResolvedValue(emptySnapshot)
    syncListTasksFromSnapshot(emptySnapshot)

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: detailShellStub,
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="tasks-detail-stub"]').text()).toBe('empty')
  })

  it('calls createTaskComment when nudge button is clicked', async () => {
    route.query = { filter: 'tracking' }
    vi.mocked(createTaskComment).mockResolvedValue({
      id: 'comment-1',
      task_id: 'task-overdue',
      author_id: 'user-1',
      author_email: 'employee@example.com',
      content: '【催办】请及时处理此任务',
      is_internal: false,
      attachments: [],
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskDetailShell: { template: '<div>detail</div>' },
        },
      },
    })

    await flushPromises()

    const nudgeButtons = wrapper.findAll('button').filter((node) => node.text().includes('催办'))
    expect(nudgeButtons.length).toBeGreaterThanOrEqual(2)
    await nudgeButtons[1]?.trigger('click')
    await flushPromises()

    expect(createTaskComment).toHaveBeenCalledWith('task-overdue', {
      content: '【催办】请及时处理此任务',
    })
  })
})
