<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { createReport } from '@/api/report-center'
import { uploadAttachment } from '@/api/attachments'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import type { ReportDirection, ReportTargetOption, WorkflowDefinitionOption } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

export type ComposeRecipientOption = {
  key: string
  user_id: string
  direction: ReportDirection
  label: string
}

interface Props {
  modelValue: boolean
  canCreateUpward: boolean
  canCreateDownward: boolean
  upwardTargetOptions: ReportTargetOption[]
  downwardTargetOptions: ReportTargetOption[]
  workflowDefinitionOptions: WorkflowDefinitionOption[]
  initialDirection?: ReportDirection | null
}

const props = withDefaults(defineProps<Props>(), {
  initialDirection: null,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: []
}>()

const submitting = ref(false)
const reportDraftUploading = ref(false)
const reportDraftAttachments = ref<
  Array<{ id: string; original_filename: string; mime_type: string; download_url: string | null }>
>([])

const form = reactive({
  recipient_key: '',
  title: '',
  content_md: '',
  workflow_definition_id: '',
})

const recipientOptions = computed<ComposeRecipientOption[]>(() => {
  const options: ComposeRecipientOption[] = []

  if (props.canCreateUpward) {
    for (const option of props.upwardTargetOptions) {
      options.push({
        key: `upward:${option.user_id}`,
        user_id: option.user_id,
        direction: 'upward',
        label: `上级 - ${option.label} (向上)`,
      })
    }
  }

  if (props.canCreateDownward) {
    for (const option of props.downwardTargetOptions) {
      options.push({
        key: `downward:${option.user_id}`,
        user_id: option.user_id,
        direction: 'downward',
        label: `下级 - ${option.label} (向下)`,
      })
    }
  }

  return options
})

const canCompose = computed(() => recipientOptions.value.length > 0)

const selectedRecipient = computed(() => {
  return recipientOptions.value.find((option) => option.key === form.recipient_key) ?? null
})

function resetDraftAttachments(): void {
  reportDraftAttachments.value = []
}

function resetForm(preferredDirection?: ReportDirection | null): void {
  const direction = preferredDirection ?? props.initialDirection
  const preferred = direction
    ? recipientOptions.value.find((option) => option.direction === direction)
    : recipientOptions.value[0]
  form.recipient_key = preferred?.key ?? ''
  form.title = ''
  form.content_md = ''
  form.workflow_definition_id = ''
  resetDraftAttachments()
}

function closeDrawer(): void {
  emit('update:modelValue', false)
}

function removeReportDraftAttachment(id: string): void {
  reportDraftAttachments.value = reportDraftAttachments.value.filter((attachment) => attachment.id !== id)
}

async function handleReportDraftFileChange(uploadFile: UploadFile): Promise<void> {
  const raw = uploadFile.raw
  if (!raw) {
    return
  }
  const err = validateAttachmentFile(raw)
  if (err) {
    ElMessage.error(err)
    return
  }
  reportDraftUploading.value = true
  try {
    const att = await uploadAttachment({ file: raw })
    reportDraftAttachments.value.push({
      id: att.id,
      original_filename: att.original_filename,
      mime_type: att.mime_type,
      download_url: att.download_url,
    })
    ElMessage.success('附件已加入，将在提交时绑定到汇报')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    reportDraftUploading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  const recipient = selectedRecipient.value
  if (!recipient) {
    ElMessage.warning('请选择收件人')
    return
  }
  if (!form.title.trim()) {
    ElMessage.warning('请输入主题')
    return
  }
  if (!form.content_md.trim()) {
    ElMessage.warning('请输入内容')
    return
  }

  submitting.value = true
  try {
    await createReport({
      direction: recipient.direction,
      target_user_id: recipient.user_id,
      title: form.title.trim(),
      content_md: form.content_md.trim(),
      workflow_definition_id: form.workflow_definition_id || null,
      attachment_ids:
        reportDraftAttachments.value.length > 0 ? reportDraftAttachments.value.map((attachment) => attachment.id) : undefined,
    })
    ElMessage.success(recipient.direction === 'upward' ? '汇报已发起' : '传达已发起')
    resetForm()
    emit('created')
    closeDrawer()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      resetForm(props.initialDirection)
    }
  },
)

watch(
  () => [props.upwardTargetOptions, props.downwardTargetOptions, props.canCreateUpward, props.canCreateDownward],
  () => {
    if (props.modelValue && !recipientOptions.value.some((option) => option.key === form.recipient_key)) {
      resetForm(props.initialDirection)
    }
  },
)
</script>

<template>
  <el-drawer
    :model-value="props.modelValue"
    title="撰写汇报"
    size="520px"
    destroy-on-close
    append-to-body
    data-testid="reports-compose-drawer"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="resetForm()"
  >
    <el-empty v-if="!canCompose" description="当前账号暂无可用的逐级上报或逐级传达链路" />

    <el-form v-else label-position="top" data-testid="reports-compose-form">
      <el-form-item label="收件人">
        <div data-testid="reports-compose-recipient" class="reports-compose-drawer__control-wrap">
          <el-select
            v-model="form.recipient_key"
            placeholder="请选择收件人"
            class="reports-compose-drawer__full-select"
            teleported
            :popper-options="{ strategy: 'fixed' }"
            popper-class="reports-compose-drawer-select-popper"
          >
            <el-option
              v-for="option in recipientOptions"
              :key="option.key"
              :label="option.label"
              :value="option.key"
            />
          </el-select>
        </div>
      </el-form-item>
      <el-form-item label="主题">
        <el-input v-model="form.title" maxlength="255" show-word-limit data-testid="reports-compose-title" />
      </el-form-item>
      <el-form-item label="内容">
        <el-input
          v-model="form.content_md"
          type="textarea"
          :rows="8"
          maxlength="4000"
          show-word-limit
          data-testid="reports-compose-content"
        />
      </el-form-item>
      <el-form-item label="附件（可选）">
        <div data-testid="reports-compose-upload">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :accept="ATTACHMENT_ACCEPT"
            :disabled="reportDraftUploading"
            :on-change="handleReportDraftFileChange"
          >
            <el-button :loading="reportDraftUploading">选择附件</el-button>
          </el-upload>
        </div>
        <div v-if="reportDraftAttachments.length" class="reports-compose-drawer__draft-tags">
          <el-tag
            v-for="attachment in reportDraftAttachments"
            :key="attachment.id"
            closable
            class="reports-compose-drawer__draft-tag"
            @close="removeReportDraftAttachment(attachment.id)"
          >
            {{ attachment.original_filename }}
          </el-tag>
        </div>
      </el-form-item>
      <el-form-item label="挂接审批流程（可选）">
        <el-select
          v-model="form.workflow_definition_id"
          clearable
          placeholder="不挂接审批"
          class="reports-compose-drawer__full-select"
          teleported
          :popper-options="{ strategy: 'fixed' }"
          popper-class="reports-compose-drawer-select-popper"
        >
          <el-option
            v-for="definition in workflowDefinitionOptions"
            :key="definition.id"
            :label="definition.name"
            :value="definition.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="reports-compose-drawer__footer">
        <el-button @click="closeDrawer">取消</el-button>
        <el-button
          type="primary"
          :disabled="!canCompose"
          :loading="submitting"
          data-testid="reports-compose-submit"
          @click="handleSubmit"
        >
          发送汇报
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.reports-compose-drawer__control-wrap {
  width: 100%;
}

.reports-compose-drawer__full-select {
  width: 100%;
}

.reports-compose-drawer__draft-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.reports-compose-drawer__footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>

<style>
.reports-compose-drawer-select-popper {
  z-index: 6000 !important;
}
</style>
