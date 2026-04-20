<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import TaskTemplatesView from '@/views/TaskTemplatesView.vue'
import TasksView from '@/views/TasksView.vue'

type TaskCenterTab = 'tasks' | 'templates'

const route = useRoute()
const router = useRouter()

const activeTab = computed<TaskCenterTab>(() => {
  return route.query.tab === 'templates' ? 'templates' : 'tasks'
})

const currentView = computed(() => {
  return activeTab.value === 'templates' ? TaskTemplatesView : TasksView
})

function handleTabChange(value: string): void {
  const nextTab: TaskCenterTab = value === 'templates' ? 'templates' : 'tasks'
  void router.replace({
    name: 'task-center',
    query: {
      tab: nextTab,
    },
  })
}
</script>

<template>
  <div class="task-center-view">
    <el-card shadow="never">
      <el-tabs :model-value="activeTab" @update:model-value="handleTabChange">
        <el-tab-pane label="待办与跟踪" name="tasks" />
        <el-tab-pane label="任务模板" name="templates" />
      </el-tabs>
    </el-card>

    <component :is="currentView" />
  </div>
</template>

<style scoped>
.task-center-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
