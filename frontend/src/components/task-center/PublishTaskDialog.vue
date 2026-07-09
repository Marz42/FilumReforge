<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'

import { uploadAttachment } from '@/api/attachments'
import { createTask } from '@/api/tasks'
import type { TaskPriority } from '@/types/api'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import ScheduledDispatchForm from '@/components/task-center/ScheduledDispatchForm.vue'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import { getErrorMessage } from '@/utils/errors'

interface PublishDraftAttachment {
  id: string
  original_filename: string
}

const props = defineProps<{
  visible: boolean
  departmentOptions: Array<{ id: string; label: string }>
  userOptions: Array<{ user_id: string; email: string; real_name?: string; department_id?: string; department_name?: string; label: string }>
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: []
}>()

const taskDialogTab = ref<'single' | 'schedule'>('single')
const scheduleSubmitting = ref(false)
const publishSubmitting = ref(false)
const publishAttachmentUploading = ref(false)
const publishDraftAttachments = ref<PublishDraftAttachment[]>([])
const scheduledDispatchFormRef = ref<InstanceType<typeof ScheduledDispatchForm> | null>(null)

const publishForm = reactive({
  title: '',
  description: '',
  assignee_user_id: '',
  department_id: '',
  priority: 'medium' as TaskPriority,
  due_date: null as Date | null,
  watcher_user_ids: [] as string[],
})

const filteredPublishUserOptions = computed(() => {
  if (!publishForm.department_id) {
    return props.userOptions
  }
  return props.userOptions.filter(
    (user) => user.department_id === publishForm.department_id,
  )
})

const assigneeSelectPlaceholder = computed(() => {
  if (filteredPublishUserOptions.value.length === 0) {
    return '该部门暂无可选执行人'
  }
  return '请选择执行人'
})

const publishFormDirty = computed(
  () => publishForm.title.trim().length > 0 || publishForm.description.trim().length > 0,
)

watch(
  () => publishForm.department_id,
  () => {
    if (
      publishForm.assignee_user_id &&
      !filteredPublishUserOptions.value.some(
        (user) => user.user_id === publishForm.assignee_user_id,
      )
    ) {
      publishForm.assignee_user_id = ''
    }
  },
)

async function requestCloseTaskDialog(): Promise<boolean> {
  if (!publishFormDirty.value) {
    return true
  }
  try {
    await ElMessageBox.confirm('有未保存的内容，是否关闭？', '关闭建立任务', {
      type: 'warning',
      confirmButtonText: '关闭',
      cancelButtonText: '继续编辑',
    })
    return true
  } catch {
    return false
  }
}

async function handleTaskDialogBeforeClose(done: () => void): Promise<void> {
  if (await requestCloseTaskDialog()) {
    resetPublishForm()
    done()
  }
}

async function handleCancelTaskDialog(): Promise<void> {
  if (!(await requestCloseTaskDialog())) {
    return
  }
  emit('update:visible', false)
  resetPublishForm()
}

function resetPublishForm(): void {
  publishForm.title = ''
  publishForm.description = ''
  publishForm.assignee_user_id = ''
  publishForm.department_id = props.departmentOptions[0]?.id ?? ''
  publishForm.priority = 'medium'
  publishForm.due_date = null
  publishForm.watcher_user_ids = []
  publishDraftAttachments.value = []
}

function removePublishDraftAttachment(id: string): void {
  publishDraftAttachments.value = publishDraftAttachments.value.filter(
    (attachment) => attachment.id !== id,
  )
}

async function handlePublishDraftFileChange(uploadFile: UploadFile): Promise<void> {
  const raw = uploadFile.raw
  if (!raw) {
    return
  }
  const err = validateAttachmentFile(raw)
  if (err) {
    ElMessage.error(err)
    return
  }
  publishAttachmentUploading.value = true
  try {
    const attachment = await uploadAttachment({ file: raw })
    publishDraftAttachments.value.push({
      id: attachment.id,
      original_filename: attachment.original_filename,
    })
    ElMessage.success('附件已加入，将在建立任务时绑定')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishAttachmentUploading.value = false
  }
}

async function handlePublishTask(): Promise<void> {
  if (!publishForm.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (!publishForm.assignee_user_id) {
    ElMessage.warning('请选择执行人')
    return
  }

  publishSubmitting.value = true
  try {
    await createTask({
      title: publishForm.title.trim(),
      description: publishForm.description.trim() || null,
      assignee_id: publishForm.assignee_user_id,
      department_id: publishForm.department_id || null,
      priority: publishForm.priority,
      due_date: publishForm.due_date ? publishForm.due_date.toISOString() : null,
      attachment_ids: publishDraftAttachments.value.map((attachment) => attachment.id),
      watcher_user_ids: publishForm.watcher_user_ids,
    })
    ElMessage.success('任务已发布')
    emit('update:visible', false)
    resetPublishForm()
    emit('created')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    publishSubmitting.value = false
  }
}

async function handleScheduleCreated(): Promise<void> {
  emit('update:visible', false)
  taskDialogTab.value = 'single'
  emit('created')
}

async function handleScheduleSubmit(): Promise<void> {
  scheduleSubmitting.value = true
  try {
    await scheduledDispatchFormRef.value?.submit()
  } finally {
    scheduleSubmitting.value = false
  }
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      taskDialogTab.value = 'single'
      resetPublishForm()
    }
  },
)
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="建立任务"
    width="720px"
    align-center
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    data-testid="task-center-task-dialog"
    :before-close="handleTaskDialogBeforeClose"
    @update:model-value="(val: boolean) => emit('update:visible', val)"
  >
    <el-tabs v-model="taskDialogTab" data-testid="task-center-create-tabs">
      <el-tab-pane label="单步任务" name="single" />
      <el-tab-pane label="定时派发" name="schedule" />
    </el-tabs>

    <el-form
      v-if="taskDialogTab === 'single'"
      label-position="top"
      class="publish-task-dialog__form"
    >
      <el-form-item label="任务标题">
        <div data-testid="task-center-task-title">
          <el-input v-model="publishForm.title" placeholder="例如：完成四月客户复盘" />
        </div>
      </el-form-item>
      <el-form-item label="任务说明">
        <div data-testid="task-center-task-description" class="publish-task-dialog__control-wrap">
          <el-input
            v-model="publishForm.description"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 10 }"
            maxlength="4000"
            show-word-limit
            placeholder="补充背景、交付要求或参考信息（可选）"
          />
        </div>
      </el-form-item>
      <el-form-item label="所属部门">
        <div data-testid="task-center-task-department" class="publish-task-dialog__control-wrap">
          <el-select
            v-model="publishForm.department_id"
            class="publish-task-dialog__full-select"
            clearable
            placeholder="可选"
            teleported
            :popper-options="{ strategy: 'fixed' }"
            popper-class="task-center-view-select-popper"
          >
            <el-option
              v-for="department in departmentOptions"
              :key="department.id"
              :label="department.label"
              :value="department.id"
            />
          </el-select>
        </div>
      </el-form-item>
      <el-form-item label="执行人">
        <div data-testid="task-center-task-assignee" class="publish-task-dialog__control-wrap">
          <el-select
            v-model="publishForm.assignee_user_id"
            class="publish-task-dialog__full-select"
            :placeholder="assigneeSelectPlaceholder"
            :disabled="filteredPublishUserOptions.length === 0"
            teleported
            :popper-options="{ strategy: 'fixed' }"
            popper-class="task-center-view-select-popper"
          >
            <el-option
              v-for="user in filteredPublishUserOptions"
              :key="user.user_id"
              :label="user.label"
              :value="user.user_id"
            />
          </el-select>
        </div>
      </el-form-item>
      <el-form-item label="抄送人">
        <div data-testid="task-center-task-watchers" class="publish-task-dialog__control-wrap">
          <el-select
            v-model="publishForm.watcher_user_ids"
            class="publish-task-dialog__full-select"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择需要抄送的同事（可选）"
            teleported
            :popper-options="{ strategy: 'fixed' }"
            popper-class="task-center-view-select-popper"
          >
            <el-option
              v-for="user in filteredPublishUserOptions.filter((user) => user.user_id !== publishForm.assignee_user_id)"
              :key="user.user_id"
              :label="user.label"
              :value="user.user_id"
            />
          </el-select>
        </div>
      </el-form-item>
      <el-form-item label="附件（可选）">
        <div data-testid="task-center-task-attachments">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :accept="ATTACHMENT_ACCEPT"
            :disabled="publishAttachmentUploading"
            :on-change="handlePublishDraftFileChange"
          >
            <el-button :loading="publishAttachmentUploading">选择附件</el-button>
          </el-upload>
        </div>
        <div v-if="publishDraftAttachments.length" class="publish-task-dialog__draft-tags">
          <el-tag
            v-for="attachment in publishDraftAttachments"
            :key="attachment.id"
            closable
            class="publish-task-dialog__draft-tag"
            @close="removePublishDraftAttachment(attachment.id)"
          >
            {{ attachment.original_filename }}
          </el-tag>
        </div>
      </el-form-item>
      <el-form-item label="优先级">
        <div data-testid="task-center-task-priority" class="publish-task-dialog__control-wrap">
          <el-select
            v-model="publishForm.priority"
            class="publish-task-dialog__full-select"
            teleported
            :popper-options="{ strategy: 'fixed' }"
            popper-class="task-center-view-select-popper"
          >
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </div>
      </el-form-item>
      <el-form-item label="截止时间">
        <div data-testid="task-center-task-due-date" class="publish-task-dialog__control-wrap">
          <FilumDateTimePicker v-model="publishForm.due_date" class="publish-task-dialog__date-picker" />
        </div>
      </el-form-item>
    </el-form>

    <ScheduledDispatchForm
      v-else
      ref="scheduledDispatchFormRef"
      :department-options="departmentOptions"
      :user-options="userOptions"
      @created="handleScheduleCreated"
    />

    <template #footer>
      <div class="publish-task-dialog__footer">
        <el-button @click="handleCancelTaskDialog">取消</el-button>
        <el-button
          v-if="taskDialogTab === 'single'"
          type="primary"
          :loading="publishSubmitting"
          data-testid="task-center-task-submit"
          @click="handlePublishTask"
        >
          建立任务
        </el-button>
        <el-button
          v-else
          type="primary"
          :loading="scheduleSubmitting"
          data-testid="task-center-schedule-submit"
          @click="handleScheduleSubmit"
        >
          创建周期任务
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.publish-task-dialog__form {
  margin-top: 12px;
}

.publish-task-dialog__control-wrap {
  width: 100%;
}

.publish-task-dialog__full-select {
  width: 100%;
}

.publish-task-dialog__draft-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.publish-task-dialog__draft-tag {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.publish-task-dialog__date-picker {
  width: 100%;
}

.publish-task-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
