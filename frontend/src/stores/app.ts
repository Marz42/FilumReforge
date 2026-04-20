import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('Phase 5')
  const deliveryStatus = ref('Knowledge, AI Router & Experience 已接入')

  const headerTitle = computed(() => `${projectName.value} · ${currentPhase.value}`)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
