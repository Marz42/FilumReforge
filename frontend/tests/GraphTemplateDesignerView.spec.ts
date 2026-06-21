import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GraphTemplateDesignerView from '@/views/GraphTemplateDesignerView.vue'

const route = reactive({ params: { id: 'tpl-1' } })

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('@/composables/useTaskCenterPermissions', () => ({
  useTaskCenterPermissions: () => ({
    ensureLoaded: vi.fn().mockResolvedValue(undefined),
    canAdministerTaskTemplates: { value: true },
  }),
}))

vi.mock('@/api/workflow-graph', () => ({
  getGraphTemplateDesigner: vi.fn().mockResolvedValue({
    id: 'tpl-1',
    code: 'topic_meeting_batch_v1',
    base_code: 'topic_meeting_batch_v1',
    name: '选题会（批次）',
    description: null,
    status: 'draft',
    version: 2,
    run_kind: 'batch',
    config: { aggregate_mode: 'batch', launch_schema: { fields: [] } },
    has_instances: false,
    structure_locked: false,
    nodes: [
      {
        id: 'n1',
        node_key: 'N1_PROPOSE',
        title: '征集',
        sort_order: 1,
        assignment_mode: 'single',
        join_mode: 'all',
        config: { kind: 'multi_instance', expand_from: 'copywriters' },
      },
    ],
    edges: [
      {
        from_node_key: 'N1_PROPOSE',
        to_node_key: 'N2_AGGREGATE',
        is_reject_path: false,
        condition: {},
        priority: 0,
      },
    ],
  }),
  saveGraphTemplateDraft: vi.fn(),
  validateGraphTemplate: vi.fn().mockResolvedValue({ valid: true, errors: [] }),
  publishGraphTemplate: vi.fn(),
  forkGraphTemplateVersion: vi.fn(),
}))

describe('GraphTemplateDesignerView', () => {
  beforeEach(() => {
    route.params.id = 'tpl-1'
  })

  it('renders designer shell with template meta', async () => {
    const wrapper = mount(GraphTemplateDesignerView, {
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="graph-template-designer"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('选题会（批次）')
    expect(wrapper.find('[data-testid="designer-save"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="designer-add-edge"]').exists()).toBe(true)
  })
})
