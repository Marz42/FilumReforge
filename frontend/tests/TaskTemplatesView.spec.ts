import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/task-center', () => ({
  getTaskCenterSnapshot: vi.fn(),
}))

vi.mock('@/api/workflow-graph', () => ({
  listGraphTemplates: vi.fn(),
}))

const routerReplace = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: routerReplace,
  }),
}))

import { getTaskCenterSnapshot } from '@/api/task-center'
import { listGraphTemplates } from '@/api/workflow-graph'
import { resetTaskCenterPermissionsCache } from '@/composables/useTaskCenterPermissions'
import { useAuthStore } from '@/stores/auth'
import TaskTemplatesView from '@/views/TaskTemplatesView.vue'

const mockGraphTemplates = [
  {
    id: 'tpl-batch',
    code: 'topic_meeting_batch_v1',
    name: '选题会（批次）',
    version: 1,
    run_kind: 'batch' as const,
    config: {},
  },
]

async function mountTaskTemplatesView() {
  const wrapper = mount(TaskTemplatesView, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        TemplateInstantiateDialog: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('TaskTemplatesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetTaskCenterPermissionsCache()
    routerReplace.mockReset()
    const authStore = useAuthStore()
    authStore.user = {
      id: 'user-lead',
      email: 'demo.video.copy.lead@example.com',
      full_name: '文案负责人',
      role: 'employee',
      is_active: true,
      department_id: 'dept-1',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    authStore.accessToken = 'test-token'

    vi.mocked(listGraphTemplates).mockResolvedValue(mockGraphTemplates)
  })

  it('renders for department lead with publish permission', async () => {
    vi.mocked(getTaskCenterSnapshot).mockResolvedValue({
      permissions: {
        can_manage_templates: true,
        can_publish_task: true,
        can_publish_cross_department: false,
      },
    } as Awaited<ReturnType<typeof getTaskCenterSnapshot>>)

    const wrapper = await mountTaskTemplatesView()

    expect(wrapper.find('[data-testid="task-templates-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-templates-graph-tab"]').exists()).toBe(true)
    expect(listGraphTemplates).toHaveBeenCalled()
    expect(routerReplace).not.toHaveBeenCalled()
  })

  it('redirects when user lacks template access', async () => {
    vi.mocked(getTaskCenterSnapshot).mockResolvedValue({
      permissions: {
        can_manage_templates: false,
        can_publish_task: false,
        can_publish_cross_department: false,
      },
    } as Awaited<ReturnType<typeof getTaskCenterSnapshot>>)

    await mountTaskTemplatesView()

    expect(routerReplace).toHaveBeenCalledWith({ name: 'task-center' })
  })
})
