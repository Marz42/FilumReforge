<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { listInstanceSubmissions } from '@/api/workflow-graph'
import type { InstanceSubmissionsResponse } from '@/types/workflowVideo'
import type { WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const props = withDefaults(
  defineProps<{
    graphInstance: WorkflowGraphInstanceDetail | null
    sourceNodeKey?: string
    expectedCount?: number | null
  }>(),
  {
    sourceNodeKey: 'N1_PROPOSE',
    expectedCount: null,
  },
)

const loading = ref(false)
const submissions = ref<InstanceSubmissionsResponse['submissions']>([])

const submittedCount = computed(
  () => submissions.value.filter((item) => item.submitted_at && item.topics.length > 0).length,
)

const totalCount = computed(() => {
  if (props.expectedCount && props.expectedCount > 0) {
    return props.expectedCount
  }
  return Math.max(submissions.value.length, submittedCount.value)
})

const progressPercent = computed(() => {
  if (totalCount.value <= 0) {
    return 0
  }
  return Math.min(100, Math.round((submittedCount.value / totalCount.value) * 100))
})

const pendingAssigneeLabels = computed(() => {
  return submissions.value
    .filter((item) => !item.submitted_at || item.topics.length === 0)
    .map((item) => item.assignee_display_name || item.assignee_email || '未命名')
    .join('、')
})

const progressSummary = computed(() => {
  const pending = pendingAssigneeLabels.value
  if (submittedCount.value >= totalCount.value) {
    return `已收到 ${submittedCount.value} / ${totalCount.value} 份采集 · 全部到齐`
  }
  if (pending) {
    return `已收到 ${submittedCount.value} / ${totalCount.value} 份采集 · 待 ${pending} 提交`
  }
  return `已收到 ${submittedCount.value} / ${totalCount.value} 份采集`
})

async function loadSubmissions(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    return
  }
  loading.value = true
  try {
    const response = await listInstanceSubmissions(instanceId, props.sourceNodeKey)
    submissions.value = response.submissions
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadSubmissions()
})

watch(
  () => props.graphInstance?.id,
  () => {
    void loadSubmissions()
  },
)

defineExpose({ reload: loadSubmissions })
</script>

<template>
  <el-card
    v-if="graphInstance"
    v-loading="loading"
    shadow="never"
    class="workflow-panel"
    data-testid="video-capture-progress-panel"
  >
    <template #header>
      <div class="workflow-panel__header">
        <strong>采集进度</strong>
        <el-button link type="primary" @click="loadSubmissions">刷新</el-button>
      </div>
    </template>

    <p class="workflow-panel__summary">{{ progressSummary }}</p>
    <el-progress :percentage="progressPercent" :stroke-width="8" />

    <el-empty
      v-if="submissions.length === 0"
      description="暂无采集任务"
      :image-size="64"
    />
  </el-card>
</template>

<style scoped>
.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.workflow-panel__summary {
  margin: 0 0 8px;
  font-size: 14px;
}
</style>
