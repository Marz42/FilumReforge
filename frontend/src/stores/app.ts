import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const projectName = ref('Project Filum')
  const currentPhase = ref('统一协同工作台')
  const deliveryStatus = ref('人事、任务、汇报、消息与知识库统一入口')
  const notificationDrawerOpen = ref(false)
  const notificationDrawerMessageId = ref('')

  const headerTitle = computed(() => projectName.value)

  function openNotificationDrawer(messageId = ''): void {
    notificationDrawerMessageId.value = messageId
    notificationDrawerOpen.value = true
  }

  function closeNotificationDrawer(): void {
    notificationDrawerOpen.value = false
    notificationDrawerMessageId.value = ''
  }

  return {
    closeNotificationDrawer,
    currentPhase,
    deliveryStatus,
    headerTitle,
    notificationDrawerMessageId,
    notificationDrawerOpen,
    openNotificationDrawer,
    projectName,
  }
})
