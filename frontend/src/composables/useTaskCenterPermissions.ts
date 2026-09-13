import axios from 'axios'
import { getSessionEpoch, isCurrentSession } from '@/api/session'
import { computed, ref } from 'vue'

import { getTaskCenterSnapshot } from '@/api/task-center'
import { useAuthStore } from '@/stores/auth'
import type { TaskCenterSnapshot } from '@/types/api'

const snapshot = ref<TaskCenterSnapshot | null>(null)
const loading = ref(false)
let loadPromise: Promise<void> | null = null
let generation = 0
let controller: AbortController | undefined

export function resetTaskCenterPermissionsCache(): void {
  generation += 1
  controller?.abort()
  controller = undefined
  snapshot.value = null
  loading.value = false
  loadPromise = null
}

export function useTaskCenterPermissions() {
  const authStore = useAuthStore()

  async function ensureLoaded(): Promise<void> {
    if (!authStore.isAuthenticated) {
      return
    }
    if (snapshot.value) {
      return
    }
    if (loadPromise) {
      await loadPromise
      return
    }

    const request = ++generation
    const epoch = getSessionEpoch()
    controller = new AbortController()
    const signal = controller.signal
    const current = () => request === generation && isCurrentSession(epoch) && !signal.aborted
    loading.value = true
    const promise = getTaskCenterSnapshot(signal)
      .then((value) => { if (current()) snapshot.value = value })
      .catch((error: unknown) => { if (current() && !axios.isCancel(error)) throw error })
      .finally(() => { if (current()) { loading.value = false; loadPromise = null } })
    loadPromise = promise
    await promise
  }

  const canPublishTask = computed(() => snapshot.value?.permissions.can_publish_task ?? false)

  /** 管理员 / HR / 具备 MANAGE_TEMPLATES 的部门主管：图模板维护（name/description/config） */
  const canAdministerTaskTemplates = computed(
    () => snapshot.value?.permissions.can_manage_templates ?? false,
  )

  /** 可见任务模板入口：可实例化（含部门主管）或管理员 */
  const canAccessTaskTemplates = computed(
    () => canPublishTask.value || canAdministerTaskTemplates.value,
  )

  return {
    snapshot,
    loading,
    ensureLoaded,
    canPublishTask,
    canAdministerTaskTemplates,
    canAccessTaskTemplates,
  }
}
