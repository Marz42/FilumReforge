import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { OverviewSnapshot } from '@/types/api'

vi.mock('@/api/overview', () => ({
  archiveBoardCard: vi.fn(),
  createAnnouncement: vi.fn(),
  createBoardCard: vi.fn(),
  getOverview: vi.fn(),
  withdrawAnnouncement: vi.fn(),
}))

import {
  archiveBoardCard,
  createAnnouncement,
  createBoardCard,
  getOverview,
  withdrawAnnouncement,
} from '@/api/overview'
import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'

type HomeViewVm = {
  boardForm: {
    scope_department_id: string
    title: string
    content_md: string
  }
  announcementForm: {
    publisher_department_id: string
    title: string
    content_md: string
  }
  openBoardDialog: () => void
  openAnnouncementDialog: () => void
  submitBoardCard: () => Promise<void>
  submitAnnouncement: () => Promise<void>
  handleArchiveBoardCard: (cardId: string) => Promise<void>
  handleWithdrawAnnouncement: (announcementId: string) => Promise<void>
}

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
  task_tracking: [
    {
      task_id: 'task-2',
      title: '跟踪排期同步',
      priority: 'high',
      status: 'doing',
      due_date: '2025-01-03T10:00:00Z',
      department_name: '研发部',
      relation_types: ['关注', '流程'],
      current_stage_label: '审批：部门确认',
      current_handler_label: '部门经理',
    },
  ],
  permissions: {
    board_scope_options: [
      { id: 'company', label: '公司' },
      { id: 'dept-1', label: '研发部' },
    ],
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
    vi.mocked(createBoardCard).mockResolvedValue(overviewSnapshot.board_cards[0]!)
    vi.mocked(createAnnouncement).mockResolvedValue(overviewSnapshot.announcements[0]!)
    vi.mocked(archiveBoardCard).mockResolvedValue()
    vi.mocked(withdrawAnnouncement).mockResolvedValue()
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
          component: {
            template: '<div>task-center</div>',
          },
        },
      ],
    })
    await router.push({ name: 'overview' })
    await router.isReady()
    return router
  }

  it('renders overview sections and data', async () => {
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

    expect(wrapper.text()).toContain('本周值班安排')
    expect(wrapper.text()).toContain('办公区维护通知')
    expect(wrapper.text()).toContain('我的待办')
    expect(wrapper.text()).toContain('跟踪任务')
    expect(wrapper.text()).toContain('待办事项')
    expect(wrapper.text()).toContain('任务跟踪')
    expect(wrapper.text()).toContain('查看待办')
    expect(wrapper.text()).toContain('查看跟踪')
    wrapper.unmount()
  })

  it('navigates to the matching task center tab from summary cards', async () => {
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

    const trackingButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('查看跟踪'))
    expect(trackingButton).toBeTruthy()

    await trackingButton?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-center')
    expect(router.currentRoute.value.query.tab).toBe('tracking')
    wrapper.unmount()
  })

  it('navigates to inbox explicitly from the summary card', async () => {
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

    const inboxButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('查看待办'))
    expect(inboxButton).toBeTruthy()

    await inboxButton?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('task-center')
    expect(router.currentRoute.value.query.tab).toBe('inbox')
    wrapper.unmount()
  })

  it('submits a new board card', async () => {
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

    const vm = wrapper.vm as unknown as HomeViewVm
    vm.openBoardDialog()
    vm.boardForm.title = '研发同步'
    vm.boardForm.content_md = '请在今天下班前更新排期。'
    await vm.submitBoardCard()
    await flushPromises()

    expect(createBoardCard).toHaveBeenCalledWith({
      scope_department_id: null,
      title: '研发同步',
      content_md: '请在今天下班前更新排期。',
    })
    wrapper.unmount()
  })

  it('submits a new announcement', async () => {
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

    const vm = wrapper.vm as unknown as HomeViewVm
    vm.openAnnouncementDialog()
    vm.announcementForm.title = '全员通知'
    vm.announcementForm.content_md = '请注意机房维护窗口。'
    await vm.submitAnnouncement()
    await flushPromises()

    expect(createAnnouncement).toHaveBeenCalledWith({
      publisher_department_id: 'dept-1',
      title: '全员通知',
      content_md: '请注意机房维护窗口。',
    })
    wrapper.unmount()
  })

  it('archives a board card and withdraws an announcement', async () => {
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

    const vm = wrapper.vm as unknown as HomeViewVm
    await vm.handleArchiveBoardCard('board-1')
    await vm.handleWithdrawAnnouncement('announcement-1')
    await flushPromises()

    expect(archiveBoardCard).toHaveBeenCalledWith('board-1')
    expect(withdrawAnnouncement).toHaveBeenCalledWith('announcement-1')
    wrapper.unmount()
  })
})
