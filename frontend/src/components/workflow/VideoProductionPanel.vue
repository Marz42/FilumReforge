<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadInstance } from 'element-plus'

import { uploadAttachment } from '@/api/attachments'
import { submitTaskDeliverable } from '@/api/tasks'
import type { Task } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  task: Task
}>()

const emit = defineEmits<{
  submitted: []
}>()

const submitting = ref(false)
const note = ref('')
const selectedFile = ref<File | null>(null)
const uploadRef = ref<UploadInstance>()

function handleFileChange(uploadFile: UploadFile): void {
  selectedFile.value = uploadFile.raw ?? null
}

function handleFileRemove(): void {
  selectedFile.value = null
}

async function submit(): Promise<void> {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }

  submitting.value = true
  try {
    const attachment = await uploadAttachment({
      file: selectedFile.value,
      target_type: 'task',
      target_id: props.task.id,
      visibility: 'private',
      relation: 'deliverable',
    })
    await submitTaskDeliverable(props.task.id, {
      summary: note.value.trim() || selectedFile.value.name,
      attachment_ids: [attachment.id],
    })
    ElMessage.success('文件已上传并提交，等待验收')
    note.value = ''
    selectedFile.value = null
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
        <span class="workflow-panel__subtitle">上传文件并提交验收</span>
      </div>
    </template>

    <el-form label-position="top">
      <el-form-item label="交付文件" required>
        <el-upload
          ref="uploadRef"
          drag
          :auto-upload="false"
          :limit="1"
          data-testid="video-production-upload"
          @change="handleFileChange"
          @remove="handleFileRemove"
        >
          <div class="video-production__upload-hint">拖拽文件到此处，或点击选择</div>
        </el-upload>
      </el-form-item>
      <el-form-item label="说明（可选）">
        <el-input
          v-model="note"
          type="textarea"
          :rows="3"
          placeholder="补充脚本或成片说明"
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
