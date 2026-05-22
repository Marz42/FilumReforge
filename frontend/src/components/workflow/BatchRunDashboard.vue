<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listInstanceChildren } from '@/api/workflow-graph'
import type { WorkflowGraphInstanceSummary } from '@/types/workflowVideo'
import type { WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  graphInstance: WorkflowGraphInstanceDetail | null
}>()

const emit = defineEmits<{
  'open-task': [taskId: string]
}>()

const loading = ref(false)
const children = ref<WorkflowGraphInstanceSummary[]>([])

const forkStatus = computed(() => {
  const context = props.graphInstance?.context ?? {}
  return typeof context.fork_status === 'string' ? context.fork_status : 'pending'
})

const approvedTopics = computed(() => {
  const context = props.graphInstance?.context ?? {}
  const topics = context.approved_topics
  return Array.isArray(topics) ? topics.length : 0
})

async function loadChildren(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    children.value = []
    return
  }
  loading.value = true
  try {
    children.value = await listInstanceChildren(instanceId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    children.value = []
  } finally {
    loading.value = false
  }
}

function resolveChildTitle(child: WorkflowGraphInstanceSummary): string {
  const context = child.context ?? {}
  const title = context.topic_title
  if (typeof title === 'string' && title.trim()) {
    return title
  }
  return child.run_label ?? child.id.slice(0, 8)
}

function resolveRootTaskId(child: WorkflowGraphInstanceSummary): string | null {
  const rootTaskId = child.context?.root_task_id
  return typeof rootTaskId === 'string' ? rootTaskId : null
}

onMounted(() => {
  void loadChildren()
})

watch(
  () => props.graphInstance?.id,
  () => {
    void loadChildren()
  },
)
</script>

<template>
  <el-card
    v-if="graphInstance"
    v-loading="loading"
    shadow="never"
    class="workflow-panel"
    data-testid="batch-run-dashboard"
  >
    <template #header>
      <div class="workflow-panel__header">
        <strong>批次制作看板</strong>
        <el-space wrap>
          <el-tag effect="plain">已通过 {{ approvedTopics }} 题</el-tag>
          <el-tag :type="forkStatus === 'completed' ? 'success' : 'warning'" effect="plain">
            fork {{ forkStatus }}
          </el-tag>
        </el-space>
      </div>
    </template>

    <el-empty v-if="children.length === 0" description="暂无子制作流，汇总派发后将自动 fork" />

    <el-table v-else :data="children" border size="small">
      <el-table-column label="选题" min-width="180">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          {{ resolveChildTitle(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="current_node_key" label="当前节点" width="140" />
      <el-table-column label="进度" width="100">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          {{ row.progress_percent ?? 0 }}%
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }: { row: WorkflowGraphInstanceSummary }">
          <el-button
            v-if="resolveRootTaskId(row)"
            link
            type="primary"
            @click="emit('open-task', resolveRootTaskId(row)!)"
          >
            打开
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="workflow-panel__actions">
      <el-button @click="loadChildren">刷新子流</el-button>
    </div>
  </el-card>
</template>

<style scoped>
.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.workflow-panel__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
