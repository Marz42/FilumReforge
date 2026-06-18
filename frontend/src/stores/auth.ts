import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  acceptInvitation,
  bootstrapAdmin,
  getBootstrapStatus,
  getInvitationPreview,
  login,
  logout as logoutSession,
  refreshSession,
  type AcceptInvitationPayload,
  type BootstrapAdminPayload,
  type LoginPayload,
} from '@/api/auth'
import { clearAuthSession, getAccessToken, setAccessToken } from '@/api/session'
import { resetTaskCenterPermissionsCache } from '@/composables/useTaskCenterPermissions'
import type { AuthSession, User, UserInvitationPreview } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(getAccessToken())
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const bootstrapRequired = ref(true)
  const bootstrapStatusLoaded = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value && accessToken.value))
  const isManagementRole = computed(
    () => user.value?.role === 'admin' || user.value?.role === 'hr',
  )

  function applySession(session: AuthSession) {
    resetTaskCenterPermissionsCache()
    accessToken.value = session.access_token
    user.value = session.user
    setAccessToken(session.access_token)
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

    try {
      applySession(await refreshSession())
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function fetchInvitationPreview(token: string): Promise<UserInvitationPreview> {
    return getInvitationPreview(token)
  }

  async function acceptInvitationRegistration(payload: AcceptInvitationPayload): Promise<User> {
    const session = await acceptInvitation(payload)
    applySession(session)
    return session.user
  }

  function clearSession(): void {
    accessToken.value = null
    user.value = null
    initialized.value = true
    clearAuthSession()
    resetTaskCenterPermissionsCache()
  }

  async function logout(): Promise<void> {
    try {
      await logoutSession()
    } finally {
      clearSession()
    }
  }

  return {
    accessToken,
    user,
    initialized,
    bootstrapRequired,
    bootstrapStatusLoaded,
    isAuthenticated,
    isManagementRole,
    login: loginWithPassword,
    bootstrapAdmin: bootstrapAdminAccount,
    fetchBootstrapStatus,
    fetchInvitationPreview,
    acceptInvitation: acceptInvitationRegistration,
    restoreSession,
    clearSession,
    logout,
  }
})
