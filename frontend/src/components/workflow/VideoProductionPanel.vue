<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'

import { uploadAttachment } from '@/api/attachments'
import { submitTaskDeliverable } from '@/api/tasks'
import type { Task } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const props = withDefaults(
  defineProps<{
    task: Task
    mode?: 'single' | 'multi' | 'platform'
    maxFiles?: number
  }>(),
  {
    mode: 'single',
    maxFiles: 10,
  },
)

const emit = defineEmits<{
  submitted: []
}>()

const submitting = ref(false)
const note = ref('')
const selectedFiles = ref<File[]>([])
const uploadRef = ref<UploadInstance>()

const uploadLimit = computed(() => (props.mode === 'multi' ? props.maxFiles : 1))
const fileRequired = computed(() => props.mode !== 'platform')
const panelSubtitle = computed(() => {
  if (props.mode === 'multi') {
    return '上传配音文件（可多选）并提交'
  }
  if (props.mode === 'platform') {
    return '上传平台链接截图，或在说明中填写视频链接'
  }
  return '上传文件并提交验收'
})

function handleFileChange(_uploadFile: UploadFile, uploadFiles: UploadFile[]): void {
  selectedFiles.value = uploadFiles
    .map((item) => item.raw)
    .filter((file): file is File => file instanceof File)
}

function handleFileRemove(_uploadFile: UploadFile, uploadFiles: UploadFile[]): void {
  selectedFiles.value = uploadFiles
    .map((item) => item.raw)
    .filter((file): file is File => file instanceof File)
}

function hasPlatformLink(value: string): boolean {
  const trimmed = value.trim()
  return trimmed.startsWith('http://') || trimmed.startsWith('https://')
}

async function submit(): Promise<void> {
  const trimmedNote = note.value.trim()
  if (fileRequired.value && selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  if (props.mode === 'platform' && selectedFiles.value.length === 0 && !hasPlatformLink(trimmedNote)) {
    ElMessage.warning('请上传截图或在说明中填写平台视频链接')
    return
  }

  submitting.value = true
  try {
    const attachmentIds: string[] = []
    for (const file of selectedFiles.value) {
      const attachment = await uploadAttachment({
        file,
        target_type: 'task',
        target_id: props.task.id,
        visibility: 'private',
        relation: 'deliverable',
      })
      attachmentIds.push(attachment.id)
    }

    const summary =
      trimmedNote
      || selectedFiles.value.map((file) => file.name).join('、')
      || '平台交付'

    await submitTaskDeliverable(props.task.id, {
      summary,
      attachment_ids: attachmentIds,
    })

    const metadata = props.task.extra_metadata as Record<string, unknown> | undefined
    const isTemplateGraph = props.task.source_type === 'template'
      && typeof metadata?.workflow_graph_instance_id === 'string'
    ElMessage.success(isTemplateGraph ? '文件已提交，流程将进入下一环节' : '文件已上传并提交，等待验收')
    note.value = ''
    selectedFiles.value = []
    uploadRef.value?.clearFiles()
    emit('submitted')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

defineExpose({ submit, submitting })
</script>

<template>
  <el-card shadow="never" class="workflow-panel" data-testid="video-production-panel">
    <template #header>
      <div class="workflow-panel__header">
        <strong>制作交付</strong>
        <span class="workflow-panel__subtitle">{{ panelSubtitle }}</span>
      </div>
    </template>

    <el-form label-position="top">
      <el-form-item :label="mode === 'platform' ? '截图或文件（可选）' : '交付文件'" :required="fileRequired">
        <el-upload
          ref="uploadRef"
          drag
          multiple
          :auto-upload="false"
          :limit="uploadLimit"
          data-testid="video-production-upload"
          @change="handleFileChange"
          @remove="handleFileRemove"
        >
          <div class="video-production__upload-hint">
            {{ mode === 'multi' ? '可拖拽多个配音文件' : '拖拽文件到此处，或点击选择' }}
          </div>
        </el-upload>
      </el-form-item>
      <el-form-item :label="mode === 'platform' ? '平台链接或说明' : '说明（可选）'">
        <el-input
          v-model="note"
          type="textarea"
          :rows="3"
          :placeholder="mode === 'platform' ? '填写视频平台链接或补充说明' : '补充脚本或成片说明'"
          data-testid="video-production-note"
        />
      </el-form-item>
      <el-button
        type="primary"
        :loading="submitting"
        data-testid="video-production-submit"
        @click="submit"
      >
        上传并提交
      </el-button>
    </el-form>
  </el-card>
</template>

<style scoped>
.workflow-panel {
  margin-bottom: 16px;
}

.workflow-panel__header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.workflow-panel__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.video-production__upload-hint {
  padding: 12px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
