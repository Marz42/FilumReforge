import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return {
    ...actual,
    ElMessageBox: {
      ...actual.ElMessageBox,
      confirm: vi.fn().mockResolvedValue(undefined),
    },
  }
})

vi.mock('@/api/task-center', () => ({ getTaskCenterSnapshot: vi.fn().mockResolvedValue({ publish_department_options: [] }) }))
vi.mock('@/api/profiles', () => ({ getProfile: vi.fn() }))
vi.mock('@/api/workflow-graph', () => ({
  listGraphTemplates: vi.fn(),
  archiveGraphTemplate: vi.fn(),
  createBlankGraphTemplate: vi.fn(),
  cloneGraphTemplate: vi.fn(),
  deleteGraphTemplate: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: null }) }))

import { archiveGraphTemplate, listGraphTemplates } from '@/api/workflow-graph'
import GraphTemplatesPanel from '@/components/workflow/GraphTemplatesPanel.vue'

describe('GraphTemplatesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listGraphTemplates).mockResolvedValue([
      {
        id: 'tpl-active',
        code: 'demo_v1',
        name: 'Demo',
        status: 'active',
        version: 1,
        tags: ['视频'],
        capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
      },
    ])
    vi.mocked(archiveGraphTemplate).mockResolvedValue({
      id: 'tpl-active',
      status: 'archived',
      nodes: [],
      edges: [],
    } as Awaited<ReturnType<typeof archiveGraphTemplate>>)
  })

  it('loads with working status filter by default', async () => {
    mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true } },
    })
    await flushPromises()
    expect(listGraphTemplates).toHaveBeenCalledWith({
      manage: true,
      status: ['draft', 'active'],
      q: '',
    })
  })

  it('renders archive button for active templates', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true } },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="graph-template-archive"]').exists()).toBe(true)
  })

  it('calls archiveGraphTemplate when archive is confirmed', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true } },
    })
    await flushPromises()
    await wrapper.find('[data-testid="graph-template-archive"]').trigger('click')
    await flushPromises()
    expect(archiveGraphTemplate).toHaveBeenCalledWith('tpl-active')
    expect(listGraphTemplates).toHaveBeenCalledTimes(2)
  })
})
