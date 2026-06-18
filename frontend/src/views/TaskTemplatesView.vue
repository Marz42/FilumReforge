<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useTaskCenterPermissions } from '@/composables/useTaskCenterPermissions'
import GraphTemplatesPanel from '@/components/workflow/GraphTemplatesPanel.vue'

const router = useRouter()
const pageReady = ref(false)
const {
  ensureLoaded,
  loading: permissionsLoading,
  canPublishTask,
  canAdministerTaskTemplates,
  canAccessTaskTemplates,
} = useTaskCenterPermissions()

const canPublish = computed(() => canPublishTask.value)

function handleGraphTemplateInstantiated(payload: { instanceId: string; rootTaskId: string }): void {
  ElMessage.success('模板已派发，正在打开跟踪视图')
  void router.push({
    path: '/task-center',
    query: {
      filter: 'tracking',
      selected: payload.rootTaskId,
    },
  })
}

onMounted(async () => {
  await ensureLoaded()
  if (!canAccessTaskTemplates.value) {
    ElMessage.warning('当前账号无权访问任务模板')
    void router.replace({ name: 'task-center' })
    return
  }
  pageReady.value = true
})
</script>

<template>
  <div
    v-if="pageReady"
    class="page"
    data-testid="task-templates-page"
    v-loading="permissionsLoading"
  >
    <GraphTemplatesPanel
      :can-publish="canPublish"
      :can-manage="canAdministerTaskTemplates"
      data-testid="task-templates-graph-tab"
      @instantiated="handleGraphTemplateInstantiated"
    />
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
