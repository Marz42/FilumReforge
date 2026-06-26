<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  listDepartmentPoolMemberOptions,
  listManagedDepartmentMemberOptions,
  submitTaskTopicCapture,
} from '@/api/workflow-graph'
import type { Task, WorkflowGraphInstanceDetail } from '@/types/api'
import type { CaptureSchema, ParticipantUserPreview } from '@/types/workflowVideo'
import { getErrorMessage } from '@/utils/errors'
import { formatUserOptionLabel } from '@/utils/userDisplay'
import { resolveCaptureSchema, isCaptureClosed, resolveUserPoolKey } from '@/utils/workflowVideoSchema'

const props = defineProps<{
  task: Task
  graphInstance: WorkflowGraphInstanceDetail | null
}>()

const emit = defineEmits<{
  submitted: []
}>()

const submitting = ref(false)
const managerLoading = ref(false)
const managerCandidates = ref<ParticipantUserPreview[]>([])
const rows = ref<Array<Record<string, string>>>([])

const nodeKey = computed(() => {
  const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
  return typeof metadata?.template_node_key === 'string' ? metadata.template_node_key : ''
})

const captureSchema = computed(() =>
  resolveCaptureSchema(props.graphInstance?.context, nodeKey.value),
)

const captureClosed = computed(() => isCaptureClosed(props.graphInstance?.context))

const maxRows = computed(() => captureSchema.value?.max_rows ?? 20)
const minRows = computed(() => captureSchema.value?.min_rows ?? 1)

const hasUserColumn = computed(() =>
  captureSchema.value?.columns.some((column) => column.type === 'user') ?? false,
)

const userPoolKey = computed(() =>
  resolveUserPoolKey(props.graphInstance?.context, nodeKey.value),
)

const graphInstanceId = computed(() => props.graphInstance?.id ?? '')

const templateId = computed(() => {
  const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
  const fromTask = typeof metadata?.template_id === 'string' ? metadata.template_id : ''
  if (fromTask) {
    return fromTask
  }
  return props.graphInstance?.template_id ?? ''
})

const userOptions = computed(() =>
  managerCandidates.value.map((user) => ({
    value: user.id,
    label: formatUserOptionLabel(user),
  })),
)

function emptyRow(schema: CaptureSchema): Record<string, string> {
  return Object.fromEntries(schema.columns.map((column) => [column.key, '']))
}

function resetRows(): void {
  const schema = captureSchema.value
  if (!schema) {
    rows.value = []
    return
  }
  rows.value = [emptyRow(schema)]
}

async function loadManagerOptions(): Promise<void> {
  if (!hasUserColumn.value) {
    return
  }
  managerLoading.value = true
  try {
    if (userPoolKey.value && templateId.value) {
      managerCandidates.value = await listDepartmentPoolMemberOptions(
        templateId.value,
        userPoolKey.value,
        graphInstanceId.value || undefined,
      )
      return
    }
    managerCandidates.value = await listManagedDepartmentMemberOptions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    managerCandidates.value = []
  } finally {
    managerLoading.value = false
  }
}

function addRow(): void {
  const schema = captureSchema.value
  if (!schema) {
    return
  }
  if (rows.value.length >= maxRows.value) {
    ElMessage.warning(`最多提交 ${maxRows.value} 行`)
    return
  }
  rows.value.push(emptyRow(schema))
}

function removeRow(index: number): void {
  if (rows.value.length <= minRows.value) {
    ElMessage.warning(`至少保留 ${minRows.value} 行`)
    return
  }
  rows.value.splice(index, 1)
}

async function handleSubmit(): Promise<void> {
  if (captureClosed.value) {
    ElMessage.warning('采集已结束，无法提交')
    return
  }
  const schema = captureSchema.value
  if (!schema) {
    ElMessage.error('当前节点未配置采集表单')
    return
  }

  const topics = rows.value.map((row) => {
    const payload: Record<string, string | null> = {}
    for (const column of schema.columns) {
      const raw = row[column.key]?.trim?.() ?? row[column.key] ?? ''
      payload[column.key] = raw || null
    }
    return payload
  })

  const filtered = topics.filter((topic) =>
    schema.columns.some((column) => {
      const value = topic[column.key]
      return value != null && String(value).trim() !== ''
    }),
  )

  if (filtered.length < minRows.value) {
    ElMessage.warning(`请至少填写 ${minRows.value} 条记录`)
    return
  }

  for (const column of schema.columns) {
    if (!column.required) {
      continue
    }
    const missing = filtered.some((topic) => {
      const value = topic[column.key]
      return value == null || String(value).trim() === ''
    })
    if (missing) {
      ElMessage.warning(`请填写必填列：${column.label}`)
      return
    }
  }

  submitting.value = true
  try {
    await submitTaskTopicCapture(props.task.id, filtered)
    ElMessage.success(`已提交 ${filtered.length} 条记录`)
    emit('submitted')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

watch(captureSchema, () => {
  resetRows()
  void loadManagerOptions()
}, { immediate: true })

onMounted(() => {
  void loadManagerOptions()
})
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
        <strong>{{ nodeKey.includes('SCHEDULE') ? '排期信息' : '表格采集' }}</strong>
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
        <template #default="{ row }: { row: Record<string, string> }">
          <el-select
            v-if="column.type === 'user'"
            v-model="row[column.key]"
            filterable
            clearable
            :loading="managerLoading"
            placeholder="选择成员"
            style="width: 100%"
          >
            <el-option
              v-for="option in userOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-input
            v-else-if="column.type === 'textarea'"
            v-model="row[column.key]"
            type="textarea"
            :rows="2"
          />
          <el-date-picker
            v-else-if="column.type === 'datetime'"
            v-model="row[column.key]"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss[Z]"
            placeholder="选择日期时间"
            style="width: 100%"
          />
          <el-input v-else v-model="row[column.key]" />
        </template>
      </el-table-column>
      <el-table-column v-if="maxRows > 1" label="操作" width="72" fixed="right">
        <template #default="{ $index }">
          <el-button link type="danger" @click="removeRow($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="workflow-panel__actions">
      <el-button v-if="maxRows > 1" @click="addRow">添加行</el-button>
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
