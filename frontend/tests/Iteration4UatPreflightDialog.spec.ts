import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/workflow-graph', () => ({
  getIteration4UatPreflight: vi.fn(),
}))

import { getIteration4UatPreflight } from '@/api/workflow-graph'
import Iteration4UatPreflightDialog from '@/components/workflow/Iteration4UatPreflightDialog.vue'

describe('Iteration4UatPreflightDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getIteration4UatPreflight).mockResolvedValue({
      generated_at: '2026-08-10T00:00:00Z',
      preflight_ready: true,
      manual_uat_required: true,
      blocking_count: 0,
      warning_count: 1,
      checks: [
        {
          check_id: 'P-03',
          area: 'templates',
          status: 'pass',
          title: '非视频通用模板',
          detail: '已找到通用模板。',
        },
        {
          check_id: 'P-07',
          area: 'manual',
          status: 'manual',
          title: '人工业务验收',
          detail: '准备检查不代表 UAT 通过。',
          action: '请按清单执行。',
        },
      ],
      template_candidates: [
        {
          kind: 'domain_neutral',
          template_id: 'template-id',
          code: 'material_collection_v1',
          name: '材料收集',
          status: 'active',
          scope_mode: 'global',
          scope_department_ids: [],
        },
      ],
      department_candidates: [
        {
          department_id: 'department-id',
          department_name: '内容部',
          active_member_count: 3,
          manager_user_id: 'manager-id',
        },
      ],
      stats_sample: {
        start_date: '2026-08-01',
        end_date: '2026-08-31',
        created_count: 4,
        completed_count: 2,
        due_count: 3,
        current_open_count: 2,
      },
    })
  })

  it('shows preparation status without claiming manual UAT passed', async () => {
    const wrapper = mount(Iteration4UatPreflightDialog, {
      props: { modelValue: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    expect(getIteration4UatPreflight).toHaveBeenCalledOnce()
    expect(document.body.textContent).toContain('环境已具备人工验收前置条件')
    expect(document.body.textContent).toContain('本检查只确认环境和样本是否可测')
    expect(document.body.textContent).toContain('人工业务验收')
    expect(document.body.textContent).toContain('内容部 · 3 名活跃成员')
    wrapper.unmount()
  })

  it('opens a suggested template from the candidate list', async () => {
    const wrapper = mount(Iteration4UatPreflightDialog, {
      props: { modelValue: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    const button = Array.from(document.body.querySelectorAll('button')).find((item) =>
      item.textContent?.includes('打开模板'),
    )
    button?.click()
    await flushPromises()

    expect(wrapper.emitted('openTemplate')?.[0]).toEqual(['template-id'])
    wrapper.unmount()
  })
})
