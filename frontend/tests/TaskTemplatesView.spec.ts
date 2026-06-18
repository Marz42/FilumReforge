import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/types/api'

vi.mock('@/api/task-center', () => ({
  getTaskCenterSnapshot: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: vi.fn(),
}))

vi.mock('@/api/workflow-graph', () => ({
  listGraphTemplates: vi.fn(),
}))

import { getTaskCenterSnapshot } from '@/api/task-center'
import { listUsers } from '@/api/users'
import { listGraphTemplates } from '@/api/workflow-graph'
import { useAuthStore } from '@/stores/auth'
import TaskTemplatesView from '@/views/TaskTemplatesView.vue'

const mockUsers: User[] = [
  {
    id: 'user-admin',
    email: 'admin@example.com',
    full_name: '管理员',
    role: 'admin',
    is_active: true,
    department_id: 'dept-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

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
    const authStore = useAuthStore()
    authStore.user = {
      id: 'user-admin',
      email: 'admin@example.com',
      full_name: '管理员',
      role: 'admin',
      is_active: true,
      department_id: 'dept-1',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }

    vi.mocked(getTaskCenterSnapshot).mockResolvedValue({
      permissions: {
        can_manage_templates: true,
        can_publish_task: true,
        can_publish_cross_department: true,
      },
    } as Awaited<ReturnType<typeof getTaskCenterSnapshot>>)
    vi.mocked(listUsers).mockResolvedValue(mockUsers)
    vi.mocked(listGraphTemplates).mockResolvedValue(mockGraphTemplates)
  })

  it('renders the unified task templates page with graph panel', async () => {
    const wrapper = await mountTaskTemplatesView()

    expect(wrapper.find('[data-testid="task-templates-page"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="task-templates-graph-tab"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('任务模板')
    expect(wrapper.text()).not.toContain('E · Legacy')
    expect(wrapper.text()).not.toContain('图模板')
  })

  it('loads graph templates for instantiation', async () => {
    await mountTaskTemplatesView()

    expect(listGraphTemplates).toHaveBeenCalled()
    expect(listUsers).toHaveBeenCalled()
  })

  it('respects canPublishTask prop without fetching task center permissions', async () => {
    vi.mocked(getTaskCenterSnapshot).mockClear()

    mount(TaskTemplatesView, {
      props: {
        canPublishTask: false,
      },
      global: {
        plugins: [ElementPlus],
        stubs: {
          TemplateInstantiateDialog: true,
        },
      },
    })
    await flushPromises()

    expect(getTaskCenterSnapshot).not.toHaveBeenCalled()
  })
})
