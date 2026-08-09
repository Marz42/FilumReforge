import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/workflow-graph', () => ({
  auditGraphTemplateGovernance: vi.fn(),
}))

import { auditGraphTemplateGovernance } from '@/api/workflow-graph'
import GraphTemplateGovernanceDialog from '@/components/workflow/GraphTemplateGovernanceDialog.vue'

describe('GraphTemplateGovernanceDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(auditGraphTemplateGovernance).mockResolvedValue({
      generated_at: '2026-08-10T00:00:00Z',
      template_count: 2,
      error_count: 1,
      warning_count: 0,
      review_count: 1,
      issues: [
        {
          issue_code: 'dependency_scope_mismatch',
          severity: 'error',
          category: 'template_dependency',
          template_id: 'parent-id',
          template_code: 'parent_v1',
          template_name: '父模板',
          template_status: 'active',
          message: '子模板范围不完整。',
          recommendation: '通过新版本修正。',
          repair_action: 'create_new_version',
          suggested_template_code: 'child_v2',
          affected_department_ids: ['department-id'],
        },
        {
          issue_code: 'global_scope_review_required',
          severity: 'review',
          category: 'availability_scope',
          template_id: 'global-id',
          template_code: 'global_v1',
          template_name: '全局模板',
          template_status: 'active',
          message: '请确认全局授权。',
          recommendation: '确认即可。',
          repair_action: 'review_configuration',
          affected_department_ids: [],
        },
      ],
    })
  })

  it('loads and renders governance findings when opened', async () => {
    const wrapper = mount(GraphTemplateGovernanceDialog, {
      props: { modelValue: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    expect(auditGraphTemplateGovernance).toHaveBeenCalledOnce()
    expect(document.body.textContent).toContain('1 项需修复')
    expect(document.body.textContent).toContain('子模板范围不完整')
    expect(document.body.textContent).toContain('建议编码：child_v2')
    wrapper.unmount()
  })

  it('emits repair for actionable findings', async () => {
    const wrapper = mount(GraphTemplateGovernanceDialog, {
      props: { modelValue: true },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flushPromises()

    const repair = document.body.querySelector<HTMLElement>('[data-testid="template-governance-repair"]')
    repair?.click()
    await flushPromises()

    expect(wrapper.emitted('repair')?.[0]?.[0]).toMatchObject({
      template_id: 'parent-id',
      repair_action: 'create_new_version',
    })
    wrapper.unmount()
  })
})
