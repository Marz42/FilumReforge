import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { User } from '@/types/api'

vi.mock('@/api/users', () => ({
  createUser: vi.fn(),
  listUsers: vi.fn(),
  updateUser: vi.fn(),
}))

import { createUser, listUsers, updateUser } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import UsersView from '@/views/UsersView.vue'

type UsersViewSetupState = {
  createForm: {
    email: string
    password: string
    role: User['role']
    status: User['status']
  }
  editForm: {
    email: string
    password: string
    role: User['role']
    status: User['status']
  }
  handleCreate: () => Promise<void>
  handleUpdate: () => Promise<void>
  openEditDialog: (user: User) => void
}

const mockUsers: User[] = [
  {
    id: 'user-1',
    email: 'admin@example.com',
    role: 'admin',
    status: 'active',
    last_login_at: '2025-01-01T12:00:00Z',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-2',
    email: 'demo.hr@example.com',
    role: 'hr',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
]

describe('Users view', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const authStore = useAuthStore()
    authStore.initialized = true
    authStore.accessToken = 'test-access-token'
    authStore.refreshToken = 'test-refresh-token'
    authStore.user = mockUsers[0] ?? null

    vi.mocked(listUsers).mockResolvedValue(mockUsers)
  })

  it('renders users and creates a new account', async () => {
    const createdUser: User = {
      id: 'user-3',
      email: 'tester@example.com',
      role: 'employee',
      status: 'active',
      last_login_at: null,
      created_at: '2025-01-03T00:00:00Z',
      updated_at: '2025-01-03T00:00:00Z',
    }
    vi.mocked(createUser).mockResolvedValue(createdUser)

    const wrapper = mount(UsersView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('用户管理')
    expect(wrapper.text()).toContain('demo.hr@example.com')
    const setupState = wrapper.vm.$.setupState as unknown as UsersViewSetupState
    setupState.createForm.email = 'tester@example.com'
    setupState.createForm.password = 'FilumTest123!'
    await setupState.handleCreate()
    await flushPromises()

    expect(createUser).toHaveBeenCalledWith({
      email: 'tester@example.com',
      password: 'FilumTest123!',
      role: 'employee',
      status: 'active',
    })
    expect(listUsers).toHaveBeenCalledTimes(2)
  })

  it('updates an existing account', async () => {
    vi.mocked(updateUser).mockResolvedValue({
      ...mockUsers[1]!,
      status: 'suspended',
    })

    const wrapper = mount(UsersView, {
      global: {
        plugins: [ElementPlus],
      },
    })

    await flushPromises()
    const setupState = wrapper.vm.$.setupState as unknown as UsersViewSetupState
    setupState.openEditDialog(mockUsers[1]!)
    setupState.editForm.password = 'ResetPass123!'
    await setupState.handleUpdate()
    await flushPromises()

    expect(updateUser).toHaveBeenCalledWith('user-2', {
      email: 'demo.hr@example.com',
      password: 'ResetPass123!',
      role: 'hr',
      status: 'active',
    })
  })
})
