<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { submitTaskTopicCapture } from '@/api/workflow-graph'
import type { Task, WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { resolveCaptureSchema } from '@/utils/workflowVideoSchema'

const props = defineProps<{
  task: Task
  graphInstance: WorkflowGraphInstanceDetail | null
}>()

const emit = defineEmits<{
  submitted: []
}>()

const submitting = ref(false)
const title = ref('')
const content = ref('')

const nodeKey = computed(() => {
  const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
  return typeof metadata?.template_node_key === 'string' ? metadata.template_node_key : ''
})

const captureSchema = computed(() =>
  resolveCaptureSchema(props.graphInstance?.context, nodeKey.value),
)

async function handleSubmit(): Promise<void> {
  if (!captureSchema.value) {
    ElMessage.error('当前节点未配置采集表单')
    return
  }
  const trimmedTitle = title.value.trim()
  if (!trimmedTitle) {
    ElMessage.warning('请填写选题标题')
    return
  }

  submitting.value = true
  try {
    await submitTaskTopicCapture(props.task.id, [
      {
        title: trimmedTitle,
        content: content.value.trim() || null,
        reason: null,
      },
    ])
    ElMessage.success('已提交选题')
    emit('submitted')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card
    v-if="captureSchema"
    shadow="never"
    class="workflow-panel"
    data-testid="template-capture-panel"
  >
    <template #header>
      <div class="workflow-panel__header">
        <strong>选题表单</strong>
        <span class="workflow-panel__subtitle">单条提交 · 每人一题</span>
      </div>
    </template>

    <el-form label-position="top">
      <el-form-item label="选题标题" required>
        <el-input v-model="title" placeholder="例如：选题A 职场效率技巧" data-testid="template-capture-title" />
      </el-form-item>
      <el-form-item label="说明（可选）">
        <el-input
          v-model="content"
          type="textarea"
          :rows="3"
          placeholder="简要说明选题角度与目标受众"
          data-testid="video-capture-content"
        />
      </el-form-item>
    </el-form>

    <div class="workflow-panel__actions">
      <el-button
        type="primary"
        :loading="submitting"
        data-testid="template-capture-submit"
        @click="handleSubmit"
      >
        提交选题
      </el-button>
    </div>
  </el-card>
</template>

<style scoped>
.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.workflow-panel__subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}

.workflow-panel__actions {
  display: flex;
  justify-content: flex-end;
}
</style>
