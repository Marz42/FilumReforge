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

vi.mock('@/api/departments', () => ({
  listDepartments: vi.fn().mockResolvedValue([]),
  listDepartmentTree: vi.fn().mockResolvedValue([]),
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
    vi.clearAllMocks()
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
    expect(wrapper.find('[data-testid="designer-launch-schema"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="designer-context-schema"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="designer-node-ui-profile"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="designer-routing-rules"]').exists()).toBe(true)
  })

  it('preserves structured authoring values in the draft payload', async () => {
    const { getGraphTemplateDesigner, saveGraphTemplateDraft } =
      await import('@/api/workflow-graph')
    const base = await getGraphTemplateDesigner('fixture')
    const configured = {
      ...base,
      context_schema: {
        type: 'object',
        properties: { amount: { type: 'number', description: '预算' } },
        required: ['amount'],
      },
      config: {
        ...base.config,
        launch_schema: {
          fields: [{ key: 'theme', label: '主题', type: 'text', required: true }],
        },
      },
      nodes: [
        {
          ...base.nodes[0]!,
          config: {
            ...base.nodes[0]!.config,
            ui_profile: 'video_n1_capture',
            routing_rules: [{ else: true, target_node_key: 'N2_AGGREGATE' }],
          },
        },
        {
          id: 'n2',
          node_key: 'N2_AGGREGATE',
          title: '汇总',
          sort_order: 2,
          assignment_mode: 'single',
          join_mode: 'all',
          config: {},
        },
      ],
    }
    vi.mocked(getGraphTemplateDesigner).mockResolvedValueOnce(configured)
    vi.mocked(saveGraphTemplateDraft).mockResolvedValueOnce(configured)

    const wrapper = mount(GraphTemplateDesignerView, {
      global: { plugins: [ElementPlus] },
    })
    await flushPromises()
    await wrapper.find('[data-testid="designer-save"]').trigger('click')
    await flushPromises()

    const payload = vi.mocked(saveGraphTemplateDraft).mock.calls[0]![1]
    expect(payload.context_schema).toEqual(configured.context_schema)
    expect(payload.config.launch_schema).toEqual(configured.config.launch_schema)
    expect(payload.nodes[0]!.config).toMatchObject({
      ui_profile: 'video_n1_capture',
      routing_rules: [{ else: true, target_node_key: 'N2_AGGREGATE' }],
    })
  })

  it('hides save-settings and shows immutability banner for active templates', async () => {
    const { getGraphTemplateDesigner } = await import('@/api/workflow-graph')
    vi.mocked(getGraphTemplateDesigner).mockResolvedValueOnce({
      id: 'tpl-1',
      code: 'topic_meeting_batch_v1',
      base_code: 'topic_meeting_batch_v1',
      name: '选题会（批次）',
      description: null,
      status: 'active',
      version: 1,
      run_kind: 'batch',
      tags: ['视频'],
      capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
      config: { aggregate_mode: 'batch', launch_schema: { fields: [] } },
      has_instances: false,
      structure_locked: false,
      nodes: [],
      edges: [],
    })
    const wrapper = mount(GraphTemplateDesignerView, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="designer-save-settings"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('不可原地修改')
  })
})
