import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('Phase A')
  const deliveryStatus = ref('文档基线已完成，工程骨架初始化中')

  const headerTitle = computed(() => `${projectName.value} · ${currentPhase.value}`)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
