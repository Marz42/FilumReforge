import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { TaskCenterSnapshot, User } from '@/types/api'

vi.mock('@/api/task-center', () => ({
  createTaskMemo: vi.fn(),
  deleteTaskMemo: vi.fn(),
  getTaskCenterSnapshot: vi.fn(),
  updateTaskMemo: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  createTask: vi.fn(),
  createTaskComment: vi.fn(),
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
  }),
}))

import { getTaskCenterSnapshot } from '@/api/task-center'
import { createTaskComment } from '@/api/tasks'
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
  template_summaries: [
    {
      id: 'template-1',
      name: '内容发布模板',
      category: 'ops',
      is_active: true,
      step_count: 3,
    },
  ],
  publish_department_options: [
    {
      id: 'dept-1',
      label: '内容部',
    },
  ],
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
  task_memos: [
    {
      id: 'memo-1',
      owner_user_id: 'user-1',
      related_task_id: 'task-2',
      content: '记得同步到团队群。',
      is_pinned: true,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-02T00:00:00Z',
      related_task: {
        id: 'task-2',
        title: '跟进视频发布',
        status: 'doing',
        priority: 'medium',
        due_date: '2025-01-04T12:00:00Z',
      },
    },
  ],
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
  })

  it('renders inbox by default and exposes global task creation from the page header', async () => {
    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-view"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-create-task"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('任务中心')
    expect(wrapper.text()).toContain('默认聚焦待处理、任务跟踪、个人备忘与任务模板')
    expect(wrapper.text()).toContain('整理四月周报')
    expect(wrapper.text()).toContain('待处理')
    expect(wrapper.text()).toContain('建立任务')
    expect(wrapper.text()).not.toContain('我的待办')
    expect(wrapper.text()).not.toContain('tracking-detail-stub')
  })

  it('renders stable selectors for the task creation drawer', async () => {
    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    const createButton = wrapper.find('[data-testid="task-center-create-task"]')
    await createButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-task-title"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-task-assignee"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-task-department"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-center-task-submit"]').exists()).toBe(true)
  })

  it('maps legacy tasks tab to tracking and updates route when tab changes', async () => {
    route.query = { tab: 'tasks' }

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-tracking-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('跟进视频发布')
    expect(wrapper.text()).toContain('待验收')
    expect(wrapper.text()).toContain('返工 1 次')
    expect(wrapper.text()).toContain('质量 4/5')
    expect(wrapper.text()).toContain('tracking-detail-stub')

    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'memos')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith({
      name: 'task-center',
      query: {
        tab: 'memos',
      },
    })
  })

  it('keeps inbox reachable as an explicit tab state', async () => {
    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="task-center-tabs"]').exists()).toBe(true)
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'inbox')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith({
      name: 'task-center',
      query: undefined,
    })
  })

  it('maps legacy history tab to tracking and keeps history visible in the tracking view', async () => {
    route.query = { tab: 'history' }

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('任务跟踪')
    expect(wrapper.text()).toContain('历史任务')
    expect(wrapper.text()).toContain('归档旧公告')
    expect(wrapper.text()).toContain('tracking-detail-stub')
  })

  it('shows overdue tag for tasks past due date', async () => {
    route.query = { tab: 'tracking' }

    const wrapper = mount(TaskCenterView, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('逾期任务示例')
    expect(wrapper.text()).toContain('已逾期')
  })

  it('calls createTaskComment when nudge button is clicked', async () => {
    route.query = { tab: 'tracking' }
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
          TaskTemplatesView: { template: '<div>templates-stub</div>' },
          TasksView: { template: '<div>tracking-detail-stub</div>' },
        },
      },
    })

    await flushPromises()

    const nudgeButtons = wrapper
      .findAll('button')
      .filter((node) => node.text().includes('催办'))
    // 第二个催办按钮对应 task-overdue（第二条 tracking 记录）
    expect(nudgeButtons.length).toBeGreaterThanOrEqual(2)
    await nudgeButtons[1]?.trigger('click')
    await flushPromises()

    expect(createTaskComment).toHaveBeenCalledWith('task-overdue', {
      content: '【催办】请及时处理此任务',
    })
  })
})
