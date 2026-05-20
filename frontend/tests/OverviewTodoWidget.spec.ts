import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { OverviewTaskInboxEntry, ReportRecord } from '@/types/api'

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

import OverviewTodoWidget from '@/components/overview/OverviewTodoWidget.vue'

const inboxTask: OverviewTaskInboxEntry = {
  task_id: 'task-1',
  title: '补齐总览首页',
  priority: 'urgent',
  status: 'todo',
  due_date: '2025-01-02T10:00:00Z',
  department_name: '研发部',
  current_stage_label: '任务：待办',
  current_handler_label: '管理员',
}

const pendingReport: ReportRecord = {
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
}

describe('OverviewTodoWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    pushMock.mockResolvedValue(undefined)
  })

  function mountWidget() {
    return mount(OverviewTodoWidget, {
      props: {
        inboxTasks: [inboxTask],
        pendingReports: [pendingReport],
      },
      global: {
        plugins: [ElementPlus],
      },
    })
  }

  it('renders inbox tasks and pending reports', () => {
    const wrapper = mountWidget()
    expect(wrapper.text()).toContain('补齐总览首页')
    expect(wrapper.text()).toContain('周报提交')
  })

  it('navigates to task center when a task row is clicked', async () => {
    const wrapper = mountWidget()
    const taskButton = wrapper
      .findAll('button.overview-widget__item')
      .find((node) => node.text().includes('补齐总览首页'))
    expect(taskButton).toBeTruthy()

    await taskButton?.trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'task-center',
      query: {
        filter: 'inbox',
        selected: 'task-1',
      },
    })
  })

  it('navigates to reports when a report row is clicked', async () => {
    const wrapper = mountWidget()
    const reportButton = wrapper
      .findAll('button.overview-widget__item')
      .find((node) => node.text().includes('周报提交'))
    expect(reportButton).toBeTruthy()

    await reportButton?.trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'reports',
      query: {
        filter: 'pending',
        selected: 'report-1',
      },
    })
  })
})
