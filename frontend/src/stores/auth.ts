import { CanceledError } from 'axios'
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
import { clearAuthSession, getAccessToken, getSessionEpoch, isCurrentSession, setAccessToken } from '@/api/session'
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

  let pendingLogout: Promise<void> | null = null
  let restorePromise: Promise<boolean> | null = null

  function applySession(session: AuthSession, epoch: number) {
    if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
    resetTaskCenterPermissionsCache()
    accessToken.value = session.access_token
    user.value = session.user
    setAccessToken(session.access_token)
    initialized.value = true
  }

  async function loginWithPassword(payload: LoginPayload): Promise<User> {
    clearSession()
    const epoch = getSessionEpoch()
    if (pendingLogout) await pendingLogout.catch(() => undefined)
    if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
    const session = await login(payload)
    applySession(session, epoch)
    return session.user
  }

  async function bootstrapAdminAccount(payload: BootstrapAdminPayload): Promise<User> {
    clearSession()
    const epoch = getSessionEpoch()
    await bootstrapAdmin(payload)
    if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
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
    if (initialized.value) return isAuthenticated.value
    if (restorePromise) return restorePromise
    const epoch = getSessionEpoch()
    const promise: Promise<boolean> = Promise.resolve().then(async () => {
      if (!isCurrentSession(epoch)) return false
      try {
        applySession(await refreshSession(), epoch)
        return true
      } catch {
        if (isCurrentSession(epoch)) clearSession()
        return false
      } finally {
        if (restorePromise === promise) restorePromise = null
      }
    })
    restorePromise = promise
    return promise
  }

  async function fetchInvitationPreview(token: string): Promise<UserInvitationPreview> {
    return getInvitationPreview(token)
  }

  async function acceptInvitationRegistration(payload: AcceptInvitationPayload): Promise<User> {
    clearSession()
    const epoch = getSessionEpoch()
    if (pendingLogout) await pendingLogout.catch(() => undefined)
    if (!isCurrentSession(epoch)) throw new CanceledError('Session changed')
    const session = await acceptInvitation(payload)
    applySession(session, epoch)
    return session.user
  }

  function clearSession(): void {
    restorePromise = null
    accessToken.value = null
    user.value = null
    initialized.value = true
    clearAuthSession()
    resetTaskCenterPermissionsCache()
  }

  async function logout(): Promise<void> {
    clearSession()
    const promise = pendingLogout ?? logoutSession()
    pendingLogout = promise
    try { await promise } finally { if (pendingLogout === promise) pendingLogout = null }
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
