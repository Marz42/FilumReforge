import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthSession, User } from '@/types/api'
import { clearAuthSession, getAccessToken } from '@/api/session'

vi.mock('@/api/auth', () => ({
  bootstrapAdmin: vi.fn(),
  getBootstrapStatus: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}))

import { bootstrapAdmin, getBootstrapStatus, login, logout, refreshSession } from '@/api/auth'
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
  token_type: 'bearer',
  user: mockUser,
}

describe('auth store', () => {
  beforeEach(() => {
    clearAuthSession()
    window.localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('stores access token in memory after login', async () => {
    vi.mocked(login).mockResolvedValue(mockSession)

    const authStore = useAuthStore()
    await authStore.login({
      email: 'admin@example.com',
      password: 'StrongPassword123!',
    })

    expect(authStore.isAuthenticated).toBe(true)
    expect(authStore.user?.email).toBe('admin@example.com')
    expect(getAccessToken()).toBe('access-token')
    expect(window.localStorage.getItem('filum.access-token')).toBeNull()
    expect(window.localStorage.getItem('filum.refresh-token')).toBeNull()
  })

  it('restores session by calling refresh endpoint', async () => {
    vi.mocked(refreshSession).mockResolvedValue(mockSession)

    const authStore = useAuthStore()
    const restored = await authStore.restoreSession()

    expect(restored).toBe(true)
    expect(authStore.user?.id).toBe('user-1')
    expect(getAccessToken()).toBe('access-token')
    expect(authStore.initialized).toBe(true)
  })

  it('clears in-memory session after logout', async () => {
    vi.mocked(login).mockResolvedValue(mockSession)
    vi.mocked(logout).mockResolvedValue()

    const authStore = useAuthStore()
    await authStore.login({
      email: 'admin@example.com',
      password: 'StrongPassword123!',
    })

    await authStore.logout()

    expect(authStore.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(vi.mocked(logout)).toHaveBeenCalledTimes(1)
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
