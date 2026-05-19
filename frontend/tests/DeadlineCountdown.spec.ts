import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const pushMock = vi.fn()

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: pushMock,
    }),
  }
})

vi.mock('@/api/overview', () => ({
  getOverview: vi.fn(),
}))

import { getOverview } from '@/api/overview'
import DeadlineCountdown from '@/components/overview/DeadlineCountdown.vue'

describe('DeadlineCountdown', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    pushMock.mockResolvedValue(undefined)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('shows countdown for the nearest future due task and navigates on click', async () => {
    const dueDate = new Date(Date.now() + 3_600_000).toISOString()
    vi.mocked(getOverview).mockResolvedValue({
      board_cards: [],
      announcements: [],
      task_inbox: [
        {
          task_id: 'task-1',
          title: '补齐总览首页',
          priority: 'urgent',
          status: 'todo',
          due_date: dueDate,
          department_name: '研发部',
          current_stage_label: '任务：待办',
          current_handler_label: '管理员',
        },
      ],
      task_tracking: [],
      permissions: {
        board_scope_options: [],
        announcement_scope_options: [],
        can_publish_board: false,
        can_publish_announcement: false,
      },
    })

    const wrapper = mount(DeadlineCountdown, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const countdown = wrapper.find('[data-testid="header-deadline-countdown"]')
    expect(countdown.exists()).toBe(true)
    expect(countdown.text()).toContain('补齐总览首页')
    expect(countdown.text()).toMatch(/\d{2}:\d{2}:\d{2}/)

    await countdown.trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'task-center',
      query: {
        filter: 'tracking',
        selected: 'task-1',
      },
    })

    wrapper.unmount()
  })

  it('hides when there is no upcoming due task', async () => {
    vi.mocked(getOverview).mockResolvedValue({
      board_cards: [],
      announcements: [],
      task_inbox: [],
      task_tracking: [],
      permissions: {
        board_scope_options: [],
        announcement_scope_options: [],
        can_publish_board: false,
        can_publish_announcement: false,
      },
    })

    const wrapper = mount(DeadlineCountdown, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="header-deadline-countdown"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
