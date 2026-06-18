<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { finalizeInstanceTopics, listInstanceSubmissions, rejectInstanceCaptures } from '@/api/workflow-graph'
import type { InstanceSubmissionsResponse } from '@/types/workflowVideo'
import type { Task, User, WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { resolveAggregateSchema } from '@/utils/workflowVideoSchema'

const props = defineProps<{
  task: Task
  graphInstance: WorkflowGraphInstanceDetail | null
  users: User[]
  canManageReject?: boolean
}>()

const emit = defineEmits<{
  finalized: []
  rejected: []
}>()

const loading = ref(false)
const submitting = ref(false)
const rejectingTopicId = ref<string | null>(null)
const submissions = ref<InstanceSubmissionsResponse['submissions']>([])

interface MatrixRow {
  topic_id: string
  title: string
  content: string
  reason: string
  submitter_label: string
  approved: boolean
  script_author_id: string
}

const matrixRows = ref<MatrixRow[]>([])

const nodeKey = computed(() => {
  const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
  return typeof metadata?.template_node_key === 'string' ? metadata.template_node_key : 'N2_AGGREGATE'
})

const aggregateSchema = computed(() =>
  resolveAggregateSchema(props.graphInstance?.context, nodeKey.value),
)

const sourceNodeKey = computed(
  () => String(aggregateSchema.value?.source_node_key ?? 'N1_PROPOSE'),
)

const userOptions = computed(() =>
  props.users
    .filter((user) => user.status === 'active')
    .map((user) => ({ value: user.id, label: user.email })),
)

const scriptAuthorOptions = computed(() => {
  const options = new Map(userOptions.value.map((option) => [option.value, option]))
  for (const row of matrixRows.value) {
    if (!row.script_author_id || options.has(row.script_author_id)) {
      continue
    }
    options.set(row.script_author_id, {
      value: row.script_author_id,
      label: row.submitter_label.includes('@') ? row.submitter_label : row.submitter_label,
    })
  }
  return [...options.values()]
})

async function loadSubmissions(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    return
  }
  loading.value = true
  try {
    const response = await listInstanceSubmissions(instanceId, sourceNodeKey.value)
    submissions.value = response.submissions
    matrixRows.value = response.submissions.flatMap((submission) =>
      submission.topics.map((topic) => ({
        topic_id: topic.topic_id ?? '',
        title: topic.title,
        content: topic.content ?? '',
        reason: topic.reason ?? '',
        submitter_label: submission.assignee_email ?? submission.assignee_user_id ?? '—',
        approved: true,
        script_author_id: submission.assignee_user_id ?? '',
      })),
    )
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleFinalize(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    return
  }
  const approved = matrixRows.value.filter((row) => row.approved && row.topic_id && row.script_author_id)
  if (approved.length === 0) {
    ElMessage.warning('请至少通过一条选题并指定脚本撰写人')
    return
  }
  const missingAuthor = approved.some((row) => !row.script_author_id)
  if (missingAuthor) {
    ElMessage.warning('每条通过的选题需指定脚本撰写人')
    return
  }

  submitting.value = true
  try {
    const result = await finalizeInstanceTopics(
      instanceId,
      approved.map((row) => ({
        topic_id: row.topic_id,
        title: row.title,
        script_author_id: row.script_author_id,
        content: row.content || null,
        reason: row.reason || null,
      })),
      matrixRows.value
        .filter((row) => !row.approved && row.topic_id)
        .map((row) => ({
          topic_id: row.topic_id,
          reason: '汇总未通过',
        })),
    )
    ElMessage.success(`已确认 ${result.approved_count} 条选题，fork：${result.fork_status}`)
    emit('finalized')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleRejectRow(row: MatrixRow): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId || !row.topic_id) {
    return
  }
  rejectingTopicId.value = row.topic_id
  try {
    await rejectInstanceCaptures(instanceId, {
      rejections: [{ topic_id: row.topic_id, reason: '汇总打回，请修改后重新提交' }],
    })
    ElMessage.success('已打回该选题')
    emit('rejected')
    await loadSubmissions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    rejectingTopicId.value = null
  }
}

onMounted(() => {
  void loadSubmissions()
})
</script>

<template>
  <el-card
    v-if="aggregateSchema"
    v-loading="loading"
    shadow="never"
    class="workflow-panel"
    data-testid="template-aggregate-panel"
  >
    <template #header>
      <div class="workflow-panel__header">
        <strong>汇总派发</strong>
        <span class="workflow-panel__subtitle">勾选通过选题并指定脚本撰写人</span>
      </div>
    </template>

    <el-empty v-if="matrixRows.length === 0 && !loading" description="暂无已提交选题，请等待采集进度更新" />

    <el-table v-else :data="matrixRows" border size="small">
      <el-table-column label="通过" width="64">
        <template #default="{ row }: { row: MatrixRow }">
          <el-checkbox v-model="row.approved" />
        </template>
      </el-table-column>
      <el-table-column prop="title" label="选题标题" min-width="160" />
      <el-table-column prop="submitter_label" label="提交人" width="140" />
      <el-table-column label="脚本撰写人" min-width="180">
        <template #default="{ row }: { row: MatrixRow }">
          <el-select
            v-model="row.script_author_id"
            filterable
            placeholder="选择撰写人"
            style="width: 100%"
            :disabled="!row.approved"
          >
            <el-option
              v-for="option in scriptAuthorOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column v-if="canManageReject" label="打回" width="88" fixed="right">
        <template #default="{ row }: { row: MatrixRow }">
          <el-button
            v-if="row.topic_id"
            type="danger"
            size="small"
            plain
            :loading="rejectingTopicId === row.topic_id"
            data-testid="template-aggregate-reject"
            @click="handleRejectRow(row)"
          >
            打回
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="workflow-panel__actions">
      <el-button @click="loadSubmissions">刷新汇总</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-testid="template-aggregate-submit"
        @click="handleFinalize"
      >
        确认派发
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
