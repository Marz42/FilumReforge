import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ReportCenterSnapshot } from '@/types/api'

vi.mock('@/api/report-center', () => ({
  actReport: vi.fn(),
  createReport: vi.fn(),
  getReportCenterSnapshot: vi.fn(),
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

import { actReport, getReportCenterSnapshot } from '@/api/report-center'
import ReportsView from '@/views/ReportsView.vue'

const mockSnapshot: ReportCenterSnapshot = {
  permissions: {
    can_create_upward: true,
    can_create_downward: true,
  },
  upward_target_options: [
    {
      user_id: 'manager-1',
      label: '直属经理',
      path_labels: ['直属经理'],
      hops: 1,
    },
  ],
  downward_target_options: [
    {
      user_id: 'member-1',
      label: '部门成员',
      path_labels: ['部门成员'],
      hops: 1,
    },
  ],
  workflow_definition_options: [
    {
      id: 'workflow-1',
      name: '汇报审批流',
    },
  ],
  pending_reports: [
    {
      id: 'report-1',
      direction: 'upward',
      status: 'in_progress',
      title: '项目周报',
      content_md: '本周完成了汇报中心联调。',
      initiator_user_id: 'user-1',
      initiator_label: '汇报员工',
      target_user_id: 'admin-1',
      target_label: '总经理',
      current_recipient_user_id: 'delegate-1',
      current_recipient_label: '代理经理',
      current_route_sequence: 1,
      workflow_definition_id: 'workflow-1',
      workflow_definition_name: '汇报审批流',
      workflow_instance_id: 'instance-1',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T01:00:00Z',
      completed_at: null,
      returned_at: null,
      archived_at: null,
      available_actions: [
        {
          action: 'advance',
          label: '继续上报',
          button_type: 'primary',
        },
      ],
      routes: [
        {
          id: 'route-1',
          sequence_no: 1,
          sender_user_id: 'user-1',
          sender_label: '汇报员工',
          recipient_user_id: 'manager-1',
          recipient_label: '直属经理',
          assigned_user_id: 'delegate-1',
          assigned_label: '代理经理',
          status: 'pending',
          activated_at: '2025-01-01T00:00:00Z',
          acted_at: null,
          note: null,
        },
      ],
    },
  ],
  initiated_reports: [],
  history_reports: [],
}

describe('Reports view', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    route.query = {}
    vi.mocked(getReportCenterSnapshot).mockResolvedValue(mockSnapshot)
    vi.mocked(actReport).mockResolvedValue(mockSnapshot.pending_reports[0]!)
  })

  it('renders pending reports by default and submits actions', async () => {
    const wrapper = mount(ReportsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('项目周报')
    expect(wrapper.text()).toContain('代理经理')
    expect(wrapper.text()).toContain('待处理')

    const actionButton = wrapper.findAll('button').find((node) => node.text().includes('继续上报'))
    expect(actionButton).toBeTruthy()
    await actionButton?.trigger('click')
    await flushPromises()

    expect(actReport).toHaveBeenCalledWith('report-1', { action: 'advance' })
  })

  it('updates route query when tab changes', async () => {
    const wrapper = mount(ReportsView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('tab-change', 'upward')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith({
      name: 'reports',
      query: {
        tab: 'upward',
      },
    })
  })
})
