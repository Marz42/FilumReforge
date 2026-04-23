import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  bootstrapAdmin,
  getBootstrapStatus,
  getCurrentUser,
  login,
  type BootstrapAdminPayload,
  type LoginPayload,
} from '@/api/auth'
import { clearAuthSession, getAccessToken, getRefreshToken, setAuthSession } from '@/api/session'
import type { User } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(getAccessToken())
  const refreshToken = ref<string | null>(getRefreshToken())
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const bootstrapRequired = ref(true)
  const bootstrapStatusLoaded = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value && accessToken.value))
  const isManagementRole = computed(
    () => user.value?.role === 'admin' || user.value?.role === 'hr',
  )

  function applySession(session: { access_token: string; refresh_token: string; user: User }) {
    accessToken.value = session.access_token
    refreshToken.value = session.refresh_token
    user.value = session.user
    setAuthSession(session.access_token, session.refresh_token)
    initialized.value = true
  }

  async function loginWithPassword(payload: LoginPayload): Promise<User> {
    const session = await login(payload)
    applySession(session)
    return session.user
  }

  async function bootstrapAdminAccount(payload: BootstrapAdminPayload): Promise<User> {
    await bootstrapAdmin(payload)
    bootstrapRequired.value = false
    bootstrapStatusLoaded.value = true
    return loginWithPassword({
      email: payload.email,
      password: payload.password,
    })
  }

  async function fetchBootstrapStatus(): Promise<boolean> {
    const status = await getBootstrapStatus()
    bootstrapRequired.value = status.bootstrap_required
    bootstrapStatusLoaded.value = true
    return status.bootstrap_required
  }

  async function restoreSession(): Promise<boolean> {
    if (initialized.value) {
      return isAuthenticated.value
    }

    accessToken.value = getAccessToken()
    refreshToken.value = getRefreshToken()

    if (!accessToken.value || !refreshToken.value) {
      initialized.value = true
      return false
    }

    try {
      user.value = await getCurrentUser()
      initialized.value = true
      return true
    } catch {
      clearSession()
      return false
    }
  }

  function clearSession(): void {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    initialized.value = true
    clearAuthSession()
  }

  function logout(): void {
    clearSession()
  }

  return {
    accessToken,
    refreshToken,
    user,
    initialized,
    bootstrapRequired,
    bootstrapStatusLoaded,
    isAuthenticated,
    isManagementRole,
    login: loginWithPassword,
    bootstrapAdmin: bootstrapAdminAccount,
    fetchBootstrapStatus,
    restoreSession,
    clearSession,
    logout,
  }
})
