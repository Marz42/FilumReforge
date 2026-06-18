<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getTaskCenterSnapshot } from '@/api/task-center'
import { listUsers } from '@/api/users'
import GraphTemplatesPanel from '@/components/workflow/GraphTemplatesPanel.vue'
import { useAuthStore } from '@/stores/auth'
import type { TaskCenterDepartmentOption, User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

interface Props {
  canManageTemplates?: boolean
  canPublishTask?: boolean
  departmentOptions?: TaskCenterDepartmentOption[]
}

const authStore = useAuthStore()
const router = useRouter()

const props = withDefaults(defineProps<Props>(), {
  canManageTemplates: undefined,
  canPublishTask: undefined,
  departmentOptions: undefined,
})

const taskCenterPermissions = ref<{ can_manage_templates: boolean; can_publish_task: boolean } | null>(
  null,
)
const loading = ref(false)
const users = ref<User[]>([])

const canPublishTask = computed(
  () =>
    props.canPublishTask
    ?? taskCenterPermissions.value?.can_publish_task
    ?? authStore.isManagementRole,
)

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

async function loadPageData(): Promise<void> {
  loading.value = true
  try {
    const [snapshot, userList] = await Promise.all([
      props.canPublishTask === undefined && props.canManageTemplates === undefined
        ? getTaskCenterSnapshot()
        : Promise.resolve(null),
      listUsers(),
    ])
    if (snapshot) {
      taskCenterPermissions.value = {
        can_manage_templates: snapshot.permissions.can_manage_templates,
        can_publish_task: snapshot.permissions.can_publish_task,
      }
    }
    users.value = userList
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadPageData()
})
</script>

<template>
  <div class="page" data-testid="task-templates-page" v-loading="loading">
    <GraphTemplatesPanel
      :users="users"
      :can-publish="canPublishTask"
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
