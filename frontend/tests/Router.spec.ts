import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/types/api'

describe('router navigation refactor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
  })

  async function seedUser(role: UserRole): Promise<void> {
    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.user = {
      id: 'user-1',
      email: 'tester@example.com',
      role,
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }
  }

  it('redirects legacy routes to the new overview, task center, reports, and people entries', async () => {
    await seedUser('admin')

    await router.push('/dashboard')
    expect(router.currentRoute.value.name).toBe('overview')

    await router.push('/task-center')
    expect(router.currentRoute.value.name).toBe('task-center')
    expect(router.currentRoute.value.query.tab).toBeUndefined()

    await router.push('/tasks')
    expect(router.currentRoute.value.name).toBe('task-center')
    expect(router.currentRoute.value.query.tab).toBe('tracking')

    await router.push('/task-templates')
    expect(router.currentRoute.value.name).toBe('task-center')
    expect(router.currentRoute.value.query.tab).toBe('templates')

    await router.push('/approvals')
    expect(router.currentRoute.value.name).toBe('reports')

    await router.push('/users')
    expect(router.currentRoute.value.name).toBe('people')
    expect(router.currentRoute.value.query.tab).toBe('users')

    await router.push('/profiles')
    expect(router.currentRoute.value.name).toBe('people')
    expect(router.currentRoute.value.query.tab).toBe('profiles')
  })

  it('prevents hr users from entering the admin-only departments route', async () => {
    await seedUser('hr')

    await router.push('/departments')
    expect(router.currentRoute.value.name).toBe('overview')
  })

  it('allows authenticated users to enter settings', async () => {
    await seedUser('employee')

    await router.push('/settings')
    expect(router.currentRoute.value.name).toBe('settings-profile')
  })
})
