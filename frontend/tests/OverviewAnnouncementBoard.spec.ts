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
  withdrawAnnouncement: vi.fn(),
}))

import {
  archiveBoardCard,
  createAnnouncement,
  createBoardCard,
  withdrawAnnouncement,
} from '@/api/overview'
import { useAuthStore } from '@/stores/auth'
import OverviewAnnouncementBoard from '@/components/overview/OverviewAnnouncementBoard.vue'

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
  task_inbox: [],
  task_tracking: [],
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

type BoardSetupState = {
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

describe('OverviewAnnouncementBoard', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.user = {
      id: 'user-1',
      email: 'admin@example.com',
      role: 'admin',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    vi.mocked(createBoardCard).mockResolvedValue(overviewSnapshot.board_cards[0]!)
    vi.mocked(createAnnouncement).mockResolvedValue(overviewSnapshot.announcements[0]!)
    vi.mocked(archiveBoardCard).mockResolvedValue()
    vi.mocked(withdrawAnnouncement).mockResolvedValue()
  })

  async function mountBoard() {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/overview', name: 'overview', component: OverviewAnnouncementBoard }],
    })
    await router.push('/overview')
    await router.isReady()

    return mount(OverviewAnnouncementBoard, {
      attachTo: document.body,
      props: {
        overview: overviewSnapshot,
      },
      global: {
        plugins: [ElementPlus, router],
        stubs: {
          transition: false,
        },
      },
    })
  }

  it('submits a new board card', async () => {
    const wrapper = await mountBoard()
    const setupState = wrapper.vm.$.setupState as unknown as BoardSetupState

    setupState.openBoardDialog()
    setupState.boardForm.title = '研发同步'
    setupState.boardForm.content_md = '请在今天下班前更新排期。'
    await setupState.submitBoardCard()
    await flushPromises()

    expect(createBoardCard).toHaveBeenCalledWith({
      scope_department_id: null,
      title: '研发同步',
      content_md: '请在今天下班前更新排期。',
    })
    wrapper.unmount()
  })

  it('submits a new announcement', async () => {
    const wrapper = await mountBoard()
    const setupState = wrapper.vm.$.setupState as unknown as BoardSetupState

    setupState.openAnnouncementDialog()
    setupState.announcementForm.title = '全员通知'
    setupState.announcementForm.content_md = '请注意机房维护窗口。'
    await setupState.submitAnnouncement()
    await flushPromises()

    expect(createAnnouncement).toHaveBeenCalledWith({
      publisher_department_id: 'dept-1',
      title: '全员通知',
      content_md: '请注意机房维护窗口。',
    })
    wrapper.unmount()
  })

  it('archives a board card and withdraws an announcement', async () => {
    const wrapper = await mountBoard()
    const setupState = wrapper.vm.$.setupState as unknown as BoardSetupState

    await setupState.handleArchiveBoardCard('board-1')
    await setupState.handleWithdrawAnnouncement('announcement-1')
    await flushPromises()

    expect(archiveBoardCard).toHaveBeenCalledWith('board-1')
    expect(withdrawAnnouncement).toHaveBeenCalledWith('announcement-1')
    wrapper.unmount()
  })
})
