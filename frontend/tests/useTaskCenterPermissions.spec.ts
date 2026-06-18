import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/task-center', () => ({
  getTaskCenterSnapshot: vi.fn(),
}))

import { getTaskCenterSnapshot } from '@/api/task-center'
import {
  resetTaskCenterPermissionsCache,
  useTaskCenterPermissions,
} from '@/composables/useTaskCenterPermissions'
import { useAuthStore } from '@/stores/auth'

describe('useTaskCenterPermissions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetTaskCenterPermissionsCache()
  })

  it('allows department leads with publish permission to access templates', async () => {
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

    vi.mocked(getTaskCenterSnapshot).mockResolvedValue({
      permissions: {
        can_manage_templates: false,
        can_publish_task: true,
        can_publish_cross_department: false,
      },
    } as Awaited<ReturnType<typeof getTaskCenterSnapshot>>)

    const permissions = useTaskCenterPermissions()
    await permissions.ensureLoaded()

    expect(permissions.canPublishTask.value).toBe(true)
    expect(permissions.canAccessTaskTemplates.value).toBe(true)
    expect(permissions.canAdministerTaskTemplates.value).toBe(false)
  })

  it('grants administer rights from task-center can_manage_templates', async () => {
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
    authStore.accessToken = 'test-token'

    vi.mocked(getTaskCenterSnapshot).mockResolvedValue({
      permissions: {
        can_manage_templates: true,
        can_publish_task: true,
        can_publish_cross_department: false,
      },
    } as Awaited<ReturnType<typeof getTaskCenterSnapshot>>)

    const permissions = useTaskCenterPermissions()
    await permissions.ensureLoaded()

    expect(permissions.canAdministerTaskTemplates.value).toBe(true)
    expect(permissions.canAccessTaskTemplates.value).toBe(true)
  })
})
