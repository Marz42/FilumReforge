import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/tasks', () => ({
  getTaskStatsScopes: vi.fn(),
  getTaskStatsSummary: vi.fn(),
  getTaskWorkload: vi.fn(),
  getTaskStatsDetails: vi.fn(),
}))

vi.mock('@/api/workflow-graph', () => ({
  listDepartmentRuns: vi.fn().mockResolvedValue([]),
  listInstanceEvents: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
}))

const route = reactive({ query: { filter: 'stats' } as Record<string, string> })
const replace = vi.fn(async ({ query }: { query: Record<string, string> }) => {
  route.query = query
})
const push = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ replace, push }),
}))

import {
  getTaskStatsDetails,
  getTaskStatsScopes,
  getTaskStatsSummary,
  getTaskWorkload,
} from '@/api/tasks'
import TaskCenterStatsView from '@/components/task-center/TaskCenterStatsView.vue'

describe('TaskCenterStatsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = { filter: 'stats' }
    vi.mocked(getTaskStatsScopes).mockResolvedValue({ mode: 'personal', departments: [] })
    vi.mocked(getTaskStatsSummary).mockResolvedValue({
      total_tasks: 8,
      completed_tasks: 3,
      completion_rate: 0.375,
      overdue_tasks: 2,
      overdue_rate: 0.4,
      tasks_by_status: { todo: 2, doing: 2, review: 1, done: 3 },
      start_date: '2026-07-01',
      end_date: '2026-07-31',
      created_tasks: 5,
      period_completed_tasks: 3,
      due_tasks: 5,
      matured_due_tasks: 5,
      on_time_completed_tasks: 3,
      on_time_completion_rate: 0.6,
      current_open_tasks: 5,
      period_overdue_tasks: 2,
    })
    vi.mocked(getTaskWorkload).mockResolvedValue([
      {
        assignee_id: 'user-1',
        assignee_email: 'member@example.com',
        assignee_label: '成员一',
        department_id: 'dept-1',
        department_name: '内容部',
        total_tasks: 8,
        open_tasks: 5,
        completed_tasks: 3,
        overdue_tasks: 2,
        created_tasks: 5,
        period_completed_tasks: 3,
        due_tasks: 5,
        matured_due_tasks: 5,
        on_time_completed_tasks: 3,
        on_time_completion_rate: 0.6,
        period_overdue_tasks: 2,
      },
    ])
    vi.mocked(getTaskStatsDetails).mockResolvedValue({
      items: [
        {
          task_id: 'task-1',
          title: '逾期任务',
          assignee_id: 'user-1',
          assignee_label: '成员一',
          department_id: 'dept-1',
          department_name: '内容部',
          source_type: 'manual',
          run_label: null,
          due_date: '2026-07-01T08:00:00Z',
          completed_at: null,
          is_overdue: true,
        },
      ],
      next_cursor: null,
      has_more: false,
    })
  })

  it('loads the personal monthly overview and renders the approved metrics', async () => {
    const wrapper = mount(TaskCenterStatsView, {
      props: { snapshot: null },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    expect(getTaskStatsSummary).toHaveBeenCalledWith(
      expect.objectContaining({ start_date: expect.any(String), end_date: expect.any(String) }),
    )
    expect(wrapper.text()).toContain('仅本人')
    expect(wrapper.text()).toContain('新增任务')
    expect(wrapper.text()).toContain('按期完成率')
    expect(wrapper.text()).toContain('成员一')
    expect(wrapper.text()).toContain('60%')
  })

  it('opens a paged metric detail and can navigate to the task', async () => {
    const wrapper = mount(TaskCenterStatsView, {
      props: { snapshot: null },
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()

    const state = wrapper.vm.$.setupState as {
      openDetails: (metric: 'overdue', title: string) => Promise<void>
      openTask: (taskId: string) => void
    }
    await state.openDetails('overdue', '逾期任务')
    await flushPromises()

    expect(getTaskStatsDetails).toHaveBeenCalledWith(
      expect.objectContaining({ metric: 'overdue', limit: 50 }),
    )
    expect(wrapper.text()).toContain('逾期任务')

    state.openTask('task-1')
    expect(push).toHaveBeenCalledWith({
      name: 'task-center',
      query: { filter: 'tracking', selected: 'task-1' },
    })
  })
})
