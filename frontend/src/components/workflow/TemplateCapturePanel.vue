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

interface CaptureRow {
  title: string
  content: string
  reason: string
}

const rows = ref<CaptureRow[]>([{ title: '', content: '', reason: '' }])

const nodeKey = computed(() => {
  const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
  return typeof metadata?.template_node_key === 'string' ? metadata.template_node_key : ''
})

const captureSchema = computed(() =>
  resolveCaptureSchema(props.graphInstance?.context, nodeKey.value),
)

const maxRows = computed(() => captureSchema.value?.max_rows ?? 20)
const minRows = computed(() => captureSchema.value?.min_rows ?? 1)

function addRow(): void {
  if (rows.value.length >= maxRows.value) {
    ElMessage.warning(`最多提交 ${maxRows.value} 行`)
    return
  }
  rows.value.push({ title: '', content: '', reason: '' })
}

function removeRow(index: number): void {
  if (rows.value.length <= minRows.value) {
    ElMessage.warning(`至少保留 ${minRows.value} 行`)
    return
  }
  rows.value.splice(index, 1)
}

async function handleSubmit(): Promise<void> {
  const schema = captureSchema.value
  if (!schema) {
    ElMessage.error('当前节点未配置采集表单')
    return
  }
  const topics = rows.value
    .map((row) => ({
      title: row.title.trim(),
      content: row.content.trim() || null,
      reason: row.reason.trim() || null,
    }))
    .filter((row) => row.title)
  if (topics.length < minRows.value) {
    ElMessage.warning(`请至少填写 ${minRows.value} 条选题`)
    return
  }
  for (const column of schema.columns) {
    if (!column.required) {
      continue
    }
    const missing = topics.some((topic) => {
      const value = (topic as Record<string, string | null>)[column.key]
      return !value?.trim?.() && !value
    })
    if (missing && column.key === 'title') {
      ElMessage.warning(`请填写必填列：${column.label}`)
      return
    }
  }

  submitting.value = true
  try {
    await submitTaskTopicCapture(props.task.id, topics)
    ElMessage.success(`已提交 ${topics.length} 条选题`)
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
        <strong>表格采集</strong>
        <span class="workflow-panel__subtitle">{{ task.title }}</span>
      </div>
    </template>

    <el-table :data="rows" border size="small">
      <el-table-column
        v-for="column in captureSchema.columns"
        :key="column.key"
        :label="column.label"
        min-width="140"
      >
        <template #default="{ row }: { row: CaptureRow }">
          <el-input
            v-if="column.type === 'textarea'"
            v-model="row[column.key as keyof CaptureRow]"
            type="textarea"
            :rows="2"
          />
          <el-input v-else v-model="row[column.key as keyof CaptureRow]" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="72" fixed="right">
        <template #default="{ $index }">
          <el-button link type="danger" @click="removeRow($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="workflow-panel__actions">
      <el-button @click="addRow">添加行</el-button>
      <el-button type="primary" :loading="submitting" data-testid="template-capture-submit" @click="handleSubmit">
        提交采集
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
  gap: 8px;
  margin-top: 12px;
}
</style>
