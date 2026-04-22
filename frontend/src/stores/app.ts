import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('Step 7')
  const deliveryStatus = ref('当前重构收口已完成，等待验测')

  const headerTitle = computed(() => `${projectName.value} · ${currentPhase.value}`)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
