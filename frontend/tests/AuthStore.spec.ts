import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthSession, User } from '@/types/api'

vi.mock('@/api/auth', () => ({
  bootstrapAdmin: vi.fn(),
  getBootstrapStatus: vi.fn(),
  getCurrentUser: vi.fn(),
  login: vi.fn(),
}))

import { bootstrapAdmin, getBootstrapStatus, getCurrentUser, login } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const mockUser: User = {
  id: 'user-1',
  email: 'admin@example.com',
  role: 'admin',
  status: 'active',
  last_login_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const mockSession: AuthSession = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
  user: mockUser,
}

describe('auth store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('stores token pair after login', async () => {
    vi.mocked(login).mockResolvedValue(mockSession)

    const authStore = useAuthStore()
    await authStore.login({
      email: 'admin@example.com',
      password: 'StrongPassword123!',
    })

    expect(authStore.isAuthenticated).toBe(true)
    expect(authStore.user?.email).toBe('admin@example.com')
    expect(window.localStorage.getItem('filum.access-token')).toBe('access-token')
    expect(window.localStorage.getItem('filum.refresh-token')).toBe('refresh-token')
  })

  it('restores persisted session', async () => {
    window.localStorage.setItem('filum.access-token', 'access-token')
    window.localStorage.setItem('filum.refresh-token', 'refresh-token')
    vi.mocked(getCurrentUser).mockResolvedValue(mockUser)

    const authStore = useAuthStore()
    const restored = await authStore.restoreSession()

    expect(restored).toBe(true)
    expect(authStore.user?.id).toBe('user-1')
    expect(authStore.initialized).toBe(true)
  })

  it('loads bootstrap status from backend', async () => {
    vi.mocked(getBootstrapStatus).mockResolvedValue({ bootstrap_required: false })

    const authStore = useAuthStore()
    const bootstrapRequired = await authStore.fetchBootstrapStatus()

    expect(bootstrapRequired).toBe(false)
    expect(authStore.bootstrapRequired).toBe(false)
    expect(authStore.bootstrapStatusLoaded).toBe(true)
  })

  it('marks bootstrap as completed after admin initialization', async () => {
    vi.mocked(bootstrapAdmin).mockResolvedValue(mockUser)
    vi.mocked(login).mockResolvedValue(mockSession)

    const authStore = useAuthStore()
    await authStore.bootstrapAdmin({
      email: 'admin@example.com',
      password: 'StrongPassword123!',
      real_name: '系统管理员',
      employee_no: 'EMP-ROOT',
    })

    expect(authStore.bootstrapRequired).toBe(false)
    expect(authStore.bootstrapStatusLoaded).toBe(true)
    expect(authStore.isAuthenticated).toBe(true)
  })
})
