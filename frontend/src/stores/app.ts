import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('Phase 1')
  const deliveryStatus = ref('系统核心业务底座开发中')

  const headerTitle = computed(() => `${projectName.value} · ${currentPhase.value}`)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
