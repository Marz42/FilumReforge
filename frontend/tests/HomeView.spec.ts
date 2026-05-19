import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { OverviewSnapshot } from '@/types/api'

vi.mock('@/api/overview', () => ({
  getOverview: vi.fn(),
}))

vi.mock('@/api/report-center', () => ({
  getReportCenterSnapshot: vi.fn(),
}))

vi.mock('@/api/messages', () => ({
  getMessageCenterSnapshot: vi.fn(),
}))

import { getOverview } from '@/api/overview'
import { getReportCenterSnapshot } from '@/api/report-center'
import { getMessageCenterSnapshot } from '@/api/messages'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'

const overviewSnapshot: OverviewSnapshot = {
  board_cards: [
    {
      id: 'board-1',
      scope_department_id: null,
      scope_label: '公司',
      title: '本周值班安排',
      content_md: '请查看本周值班表。',
      expires_at: '2025-01-08T00:00:00Z',
      author_user_id: 'user-1',
      author_name: '管理员',
      created_at: '2025-01-01T00:00:00Z',
    },
  ],
  announcements: [
    {
      id: 'announcement-1',
      publisher_department_id: 'dept-1',
      publisher_department_name: '财务行政部',
      title: '办公区维护通知',
      content_md: '今晚进行网络维护。',
      published_at: '2025-01-02T09:00:00Z',
      author_user_id: 'user-1',
      author_name: '管理员',
    },
  ],
  task_inbox: [
    {
      task_id: 'task-1',
      title: '补齐总览首页',
      priority: 'urgent',
      status: 'todo',
      due_date: '2025-01-02T10:00:00Z',
      department_name: '研发部',
      current_stage_label: '任务：待办',
      current_handler_label: '管理员',
    },
  ],
  task_tracking: [],
  permissions: {
    board_scope_options: [{ id: 'company', label: '公司' }],
    announcement_scope_options: [{ id: 'dept-1', label: '财务行政部' }],
    can_publish_board: true,
    can_publish_announcement: true,
  },
}

describe('Home view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    vi.mocked(getOverview).mockResolvedValue(overviewSnapshot)
    vi.mocked(getReportCenterSnapshot).mockResolvedValue({
      permissions: {
        can_create_upward: true,
        can_create_downward: true,
      },
      upward_target_options: [],
      downward_target_options: [],
      workflow_definition_options: [],
      pending_reports: [
        {
          id: 'report-1',
          direction: 'upward',
          status: 'in_progress',
          title: '周报提交',
          content_md: '本周进展',
          initiator_user_id: 'user-2',
          initiator_label: '工程师',
          target_user_id: 'user-1',
          target_label: '管理员',
          current_recipient_user_id: 'user-1',
          current_recipient_label: '管理员',
          current_route_sequence: 1,
          workflow_definition_id: null,
          workflow_definition_name: null,
          workflow_instance_id: null,
          created_at: '2025-01-02T08:00:00Z',
          updated_at: '2025-01-02T08:30:00Z',
          completed_at: null,
          returned_at: null,
          archived_at: null,
        },
      ],
      initiated_reports: [],
      history_reports: [],
    })
    vi.mocked(getMessageCenterSnapshot).mockResolvedValue({
      items: [
        {
          id: 'message-1',
          source_type: 'task',
          source_id: 'task-1',
          recipient_user_id: 'user-1',
          recipient_email: 'admin@example.com',
          message_type: 'assignment',
          title: '新任务指派',
          body_text: '你有一条新任务',
          body_html: null,
          payload: {},
          status: 'completed',
          scheduled_at: null,
          enqueued_at: '2025-01-02T08:00:00Z',
          completed_at: '2025-01-02T08:00:00Z',
          created_at: '2025-01-02T08:00:00Z',
          source: {
            module_label: '任务',
            target: {
              can_navigate: true,
              route_name: 'task-center',
              route_params: {},
              route_query: { selected: 'task-1' },
            },
          },
          receipt_state: {
            is_read: false,
            is_acknowledged: false,
          },
          deliveries: [],
        },
      ],
      total_count: 1,
      filtered_count: 1,
      unread_count: 1,
      unacknowledged_count: 1,
      source_counts: [],
      applied_source_type: null,
      applied_state: 'all',
      applied_channel: null,
      applied_delivery_status: null,
      applied_created_from: null,
      applied_created_to: null,
    })
  })

  async function createTestRouter() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/overview',
          name: 'overview',
          component: HomeView,
        },
        {
          path: '/task-center',
          name: 'task-center',
          component: { template: '<div>task-center</div>' },
        },
      ],
    })
    await router.push({ name: 'overview' })
    await router.isReady()
    return router
  }

  it('renders overview widgets and quick links', async () => {
    const router = await createTestRouter()
    const wrapper = mount(HomeView, {
      attachTo: document.body,
      global: {
        plugins: [ElementPlus, router],
        stubs: {
          transition: false,
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="overview-widget-messages"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-widget-announcement-board"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="overview-widget-todos"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('补齐总览首页')
    expect(wrapper.text()).toContain('周报提交')
    expect(wrapper.text()).toContain('办公区维护通知')
    expect(wrapper.text()).toContain('快捷入口')
    wrapper.unmount()
  })

  it('loads overview and report center snapshots on mount', async () => {
    const router = await createTestRouter()
    const wrapper = mount(HomeView, {
      attachTo: document.body,
      global: {
        plugins: [ElementPlus, router],
      },
    })

    await flushPromises()

    expect(getOverview).toHaveBeenCalled()
    expect(getReportCenterSnapshot).toHaveBeenCalled()
    wrapper.unmount()
  })
})
