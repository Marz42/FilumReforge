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
    vi.mocked(listGraphTemplates).mockImplementation(async (options = {}) => {
      if (options.manage) {
        return [
          {
            id: 'tpl-active',
            code: 'department_owned_v1',
            name: '本部门模板',
            status: 'active',
            version: 1,
            tags: ['视频'],
            capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
          },
        ]
      }
      return [
        {
          id: 'tpl-shared',
          code: 'shared_v1',
          name: '跨部门共享模板',
          status: 'active',
          version: 1,
          tags: ['共享'],
          capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
        },
        {
          id: 'tpl-active',
          code: 'department_owned_v1',
          name: '本部门模板',
          status: 'active',
          version: 1,
          tags: ['视频'],
          capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
        },
      ]
    })
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
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true, GraphTemplateAvailabilityDialog: true } },
    })
    await flushPromises()
    expect(listGraphTemplates).toHaveBeenCalledWith({
      manage: true,
      status: ['draft', 'active'],
      q: '',
    })
    expect(listGraphTemplates).toHaveBeenCalledWith({
      status: ['active'],
      q: '',
    })
  })

  it('shows readable shared templates without exposing management actions', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true, GraphTemplateAvailabilityDialog: true } },
    })
    await flushPromises()

    const sharedRow = wrapper.findAll('.el-table__row').find((row) => row.text().includes('跨部门共享模板'))
    expect(sharedRow).toBeDefined()
    expect(sharedRow!.find('[data-testid="graph-template-instantiate"]').exists()).toBe(true)
    expect(sharedRow!.find('[data-testid="graph-template-design"]').exists()).toBe(false)
    expect(sharedRow!.find('[data-testid="graph-template-availability"]').exists()).toBe(false)
    expect(sharedRow!.find('[data-testid="graph-template-archive"]').exists()).toBe(false)
  })

  it('renders archive button for active templates', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true, GraphTemplateAvailabilityDialog: true } },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="graph-template-archive"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="graph-template-availability"]').exists()).toBe(true)
  })

  it('calls archiveGraphTemplate when archive is confirmed', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true, GraphTemplateAvailabilityDialog: true } },
    })
    await flushPromises()
    await wrapper.find('[data-testid="graph-template-archive"]').trigger('click')
    await flushPromises()
    expect(archiveGraphTemplate).toHaveBeenCalledWith('tpl-active')
    expect(listGraphTemplates).toHaveBeenCalledTimes(4)
  })
})
