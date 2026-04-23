import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('统一协同工作台')
  const deliveryStatus = ref('人事、任务、汇报、消息与知识库统一入口')

  const headerTitle = computed(() => projectName.value)

  return {
    currentPhase,
    deliveryStatus,
    headerTitle,
    projectName,
  }
})
