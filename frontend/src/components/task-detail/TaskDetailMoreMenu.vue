<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  listInstanceSubmissions,
  rejectInstanceCaptures,
  rejectProductionStep,
} from '@/api/workflow-graph'
import type { TaskDetailProfile } from '@/domain/task-detail/profile'
import { TASK_CENTER_V2_UI_ENABLED } from '@/constants/task-center'
import type { Task, WorkflowGraphInstanceDetail } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const router = useRouter()

const props = defineProps<{
  profile: TaskDetailProfile
  task: Task | null
  graphInstance: WorkflowGraphInstanceDetail | null
  canManageCaptureReject: boolean
  canRejectProduction: boolean
}>()

const emit = defineEmits<{
  actionDone: []
}>()

const captureRejectVisible = ref(false)
const productionRejectVisible = ref(false)
const rejectReason = ref('')
const rejectTopicId = ref('')
const rejectSubmitting = ref(false)
const rejectTopicsLoading = ref(false)
const rejectTopicOptions = ref<Array<{ value: string; label: string }>>([])

const menuItems = computed(() => {
  const items: Array<{ key: string; label: string }> = []
  const profileId = props.profile.id

  if (
    props.canManageCaptureReject
    && props.graphInstance
    && (profileId === 'video_n2_aggregate' || profileId === 'video_batch_root')
  ) {
    items.push({ key: 'reject-capture', label: '打回采集…' })
  }

  if (props.canRejectProduction && props.task && profileId === 'video_production_step') {
    items.push({ key: 'reject-production', label: '退回…' })
  }

  if (TASK_CENTER_V2_UI_ENABLED && props.graphInstance && props.task) {
    items.push({ key: 'open-stats', label: '打开任务统计' })
  }

  return items
})

const showMenu = computed(() => menuItems.value.length > 0)

async function loadRejectTopicOptions(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId) {
    rejectTopicOptions.value = []
    return
  }
  rejectTopicsLoading.value = true
  try {
    const response = await listInstanceSubmissions(instanceId, 'N1_PROPOSE')
    const options: Array<{ value: string; label: string }> = []
    for (const submission of response.submissions) {
      if (!submission.submitted_at) {
        continue
      }
      for (const topic of submission.topics) {
        if (!topic.topic_id) {
          continue
        }
        options.push({
          value: topic.topic_id,
          label: `${topic.title}（${submission.assignee_display_name ?? submission.assignee_email ?? '提交人'}）`,
        })
      }
    }
    rejectTopicOptions.value = options
    rejectTopicId.value = options[0]?.value ?? ''
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    rejectTopicOptions.value = []
  } finally {
    rejectTopicsLoading.value = false
  }
}

async function openCaptureRejectDialog(): Promise<void> {
  rejectReason.value = ''
  rejectTopicId.value = ''
  captureRejectVisible.value = true
  await loadRejectTopicOptions()
}

function openProductionRejectDialog(): void {
  rejectReason.value = ''
  productionRejectVisible.value = true
}

async function handleMenuCommand(key: string): Promise<void> {
  if (key === 'reject-capture') {
    await openCaptureRejectDialog()
    return
  }
  if (key === 'reject-production') {
    openProductionRejectDialog()
    return
  }
  if (key === 'open-stats' && props.task) {
    await router.push({
      name: 'task-center',
      query: {
        filter: 'stats',
        selected: props.task.id,
      },
    })
  }
}

async function submitCaptureReject(): Promise<void> {
  const instanceId = props.graphInstance?.id
  if (!instanceId || !rejectTopicId.value) {
    ElMessage.warning('请选择要打回的选题')
    return
  }
  const reason = rejectReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写打回原因')
    return
  }

  rejectSubmitting.value = true
  try {
    await rejectInstanceCaptures(instanceId, {
      rejections: [{ topic_id: rejectTopicId.value, reason }],
    })
    ElMessage.success('已打回采集，待编辑补交')
    captureRejectVisible.value = false
    emit('actionDone')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    rejectSubmitting.value = false
  }
}

async function submitProductionReject(): Promise<void> {
  const taskId = props.task?.id
  if (!taskId) {
    return
  }
  const reason = rejectReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写退回原因')
    return
  }

  rejectSubmitting.value = true
  try {
    await rejectProductionStep(taskId, { reason })
    ElMessage.success('已退回，待重新处理')
    productionRejectVisible.value = false
    emit('actionDone')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    rejectSubmitting.value = false
  }
}
</script>

<template>
  <el-dropdown
    v-if="showMenu"
    trigger="click"
    data-testid="task-detail-more-menu"
    @command="handleMenuCommand"
  >
    <el-button>
      更多
      <span class="task-detail-more-menu__caret">▾</span>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="item in menuItems"
          :key="item.key"
          :command="item.key"
          :data-testid="`task-detail-more-${item.key}`"
        >
          {{ item.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="captureRejectVisible" title="打回采集" width="480px">
    <el-form label-position="top">
      <el-form-item label="选题" required>
        <el-select
          v-model="rejectTopicId"
          v-loading="rejectTopicsLoading"
          filterable
          placeholder="选择已提交的选题"
          style="width: 100%"
          data-testid="task-detail-reject-topic-select"
        >
          <el-option
            v-for="option in rejectTopicOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="打回原因" required>
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="3"
          placeholder="说明需要修改的方向"
          data-testid="task-detail-reject-reason"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="captureRejectVisible = false">取消</el-button>
      <el-button
        type="danger"
        :loading="rejectSubmitting"
        data-testid="task-detail-reject-capture-submit"
        @click="submitCaptureReject"
      >
        确认打回
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="productionRejectVisible" title="退回制作" width="480px">
    <el-form label-position="top">
      <el-form-item label="退回原因" required>
        <el-input
          v-model="rejectReason"
          type="textarea"
          :rows="3"
          placeholder="说明需要修改的内容"
          data-testid="task-detail-reject-production-reason"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="productionRejectVisible = false">取消</el-button>
      <el-button
        type="danger"
        :loading="rejectSubmitting"
        data-testid="task-detail-reject-production-submit"
        @click="submitProductionReject"
      >
        确认退回
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.task-detail-more-menu__caret {
  margin-left: 4px;
  font-size: 12px;
}
</style>
