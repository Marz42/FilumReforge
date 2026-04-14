import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('Phase 4')
  const deliveryStatus = ref('Workflow Engine & Messaging 开发中')

  const headerTitle = computed(() => `${projectName.value} · ${currentPhase.value}`)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
