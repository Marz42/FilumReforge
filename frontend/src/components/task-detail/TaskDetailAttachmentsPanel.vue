<script setup lang="ts">
import { ElMessage, type UploadFile } from 'element-plus'

import AttachmentActions from '@/components/attachments/AttachmentActions.vue'
import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'
import type { Attachment } from '@/types/api'

defineProps<{
  attachments: Attachment[]
  uploading: boolean
  resetKey: number
}>()

const emit = defineEmits<{
  filesChange: [files: File[]]
  upload: []
}>()

function normalizeUploadFiles(uploadFiles: UploadFile[]): File[] {
  return uploadFiles.reduce<File[]>((files, uploadFile) => {
    if (uploadFile.raw) {
      files.push(uploadFile.raw)
    }
    return files
  }, [])
}

function handleFileListChange(_uploadFile: UploadFile, uploadFiles: UploadFile[]): void {
  emit('filesChange', normalizeUploadFiles(uploadFiles))
}

function beforeUploadAttachmentFile(raw: File): boolean {
  const error = validateAttachmentFile(raw)
  if (error) {
    ElMessage.error(error)
    return false
  }
  return true
}
</script>

<template>
  <section class="attachments" data-testid="task-attachments-section">
    <div class="attachments__heading">
      <strong>任务资料附件</strong>
      <span>{{ attachments.length }} 个文件</span>
    </div>

    <div class="attachments__upload-row">
      <div data-testid="tasks-attachment-upload">
        <el-upload
          :key="resetKey"
          class="attachments__upload"
          :auto-upload="false"
          multiple
          :limit="10"
          :show-file-list="true"
          :accept="ATTACHMENT_ACCEPT"
          :before-upload="beforeUploadAttachmentFile"
          :on-change="handleFileListChange"
          :on-remove="handleFileListChange"
        >
          <template #trigger>
            <el-button>选择附件</el-button>
          </template>
        </el-upload>
      </div>

      <el-button type="primary" :loading="uploading" @click="emit('upload')">
        上传到任务
      </el-button>
    </div>

    <el-empty
      v-if="attachments.length === 0"
      :image-size="56"
      description="暂无任务资料附件"
    />

    <div v-else class="attachments__list">
      <el-card
        v-for="attachment in attachments"
        :key="attachment.id"
        shadow="never"
        class="attachments__card"
      >
        <div class="attachments__row">
          <div class="attachments__copy">
            <strong>{{ attachment.original_filename }}</strong>
            <p>{{ attachment.mime_type }} · {{ attachment.size_bytes }} bytes</p>
          </div>
          <AttachmentActions
            :attachment="attachment"
            view-test-id="task-attachment-view"
            download-test-id="task-attachment-download"
          />
        </div>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.attachments {
  width: 100%;
  box-sizing: border-box;
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-extra-light);
}

.attachments__heading,
.attachments__upload-row,
.attachments__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.attachments__heading {
  margin-bottom: 12px;
}

.attachments__heading span {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.attachments__upload-row {
  align-items: flex-start;
  margin-bottom: 12px;
}

.attachments__upload,
.attachments__card,
.attachments__copy {
  min-width: 0;
}

.attachments__list {
  display: grid;
  gap: 8px;
}

.attachments__row {
  gap: 16px;
}

.attachments__copy strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachments__copy p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

@media (max-width: 640px) {
  .attachments__upload-row,
  .attachments__row {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
