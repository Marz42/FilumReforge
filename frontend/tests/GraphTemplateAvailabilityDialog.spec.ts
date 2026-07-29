import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn(),
}))
vi.mock('@/api/workflow-graph', () => ({
  expandGraphTemplateAvailabilityScope: vi.fn(),
  listGraphTemplateAvailabilityScopeEvents: vi.fn(),
}))

import { listDepartments } from '@/api/departments'
import {
  expandGraphTemplateAvailabilityScope,
  listGraphTemplateAvailabilityScopeEvents,
} from '@/api/workflow-graph'
import GraphTemplateAvailabilityDialog from '@/components/workflow/GraphTemplateAvailabilityDialog.vue'

describe('GraphTemplateAvailabilityDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listDepartments).mockResolvedValue([
      { id: 'dept-a', name: '业务一部', code: 'a', parent_id: null, manager_id: null, sort_order: 1, is_active: true, created_at: '', updated_at: '' },
      { id: 'dept-b', name: '业务二部', code: 'b', parent_id: null, manager_id: null, sort_order: 2, is_active: true, created_at: '', updated_at: '' },
    ])
    vi.mocked(listGraphTemplateAvailabilityScopeEvents).mockResolvedValue([])
    vi.mocked(expandGraphTemplateAvailabilityScope).mockResolvedValue({
      template_id: 'tpl-1',
      scope_mode: 'departments',
      scope_department_ids: ['dept-a', 'dept-b'],
      change: {
        id: 'event-1',
        template_id: 'tpl-1',
        actor_user_id: 'admin-1',
        actor_email: 'admin@example.com',
        actor_display_name: '管理员',
        action: 'departments_added',
        before_scope_mode: 'departments',
        before_department_ids: ['dept-a'],
        after_scope_mode: 'departments',
        after_department_ids: ['dept-a', 'dept-b'],
        added_department_ids: ['dept-b'],
        reason: '新增试用部门',
        created_at: '2026-07-30T02:00:00+08:00',
      },
    })
  })

  it('loads departments and audit events for an active template', async () => {
    const wrapper = mount(GraphTemplateAvailabilityDialog, {
      props: {
        modelValue: true,
        template: {
          id: 'tpl-1',
          code: 'generic_v1',
          name: '通用流程',
          status: 'active',
          version: 1,
          scope_mode: 'departments',
          scope_department_ids: ['dept-a'],
        },
      },
      global: {
        plugins: [ElementPlus],
        stubs: { ElDialog: { template: '<div><slot /><slot name="footer" /></div>' } },
      },
    })
    await flushPromises()

    expect(listDepartments).toHaveBeenCalledOnce()
    expect(listGraphTemplateAvailabilityScopeEvents).toHaveBeenCalledWith('tpl-1')
    expect(wrapper.find('[data-testid="template-availability-departments"]').exists()).toBe(true)
  })

  it('submits an additive department expansion with reason', async () => {
    const wrapper = mount(GraphTemplateAvailabilityDialog, {
      props: {
        modelValue: true,
        template: {
          id: 'tpl-1',
          code: 'generic_v1',
          name: '通用流程',
          status: 'active',
          version: 1,
          scope_mode: 'departments',
          scope_department_ids: ['dept-a'],
        },
      },
      global: {
        plugins: [ElementPlus],
        stubs: { ElDialog: { template: '<div><slot /><slot name="footer" /></div>' } },
      },
    })
    await flushPromises()

    const select = wrapper.findComponent({ name: 'ElSelect' })
    await select.setValue(['dept-a', 'dept-b'])
    const input = wrapper.findComponent({ name: 'ElInput' })
    await input.setValue('新增试用部门')
    await wrapper.find('[data-testid="template-availability-submit"]').trigger('click')
    await flushPromises()

    expect(expandGraphTemplateAvailabilityScope).toHaveBeenCalledWith('tpl-1', {
      scope_mode: 'departments',
      scope_department_ids: ['dept-a', 'dept-b'],
      reason: '新增试用部门',
    })
    expect(wrapper.emitted('updated')).toHaveLength(1)
  })
})
