<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'

import { ATTACHMENT_ACCEPT, validateAttachmentFile } from '@/constants/attachments'

const props = defineProps<{
  collapse: boolean
  isManagementRole: boolean
  content: string
  isInternal: boolean
  submitting: boolean
  attachmentResetKey: number
}>()

const emit = defineEmits<{
  'update:content': [value: string]
  'update:isInternal': [value: boolean]
  filesChange: [files: File[]]
  submit: []
}>()

const contentModel = computed({
  get: () => props.content,
  set: (value: string) => emit('update:content', value),
})

const internalModel = computed({
  get: () => props.isInternal,
  set: (value: boolean) => emit('update:isInternal', value),
})

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
  <el-collapse v-if="collapse" class="comments-collapse">
    <el-collapse-item title="评论与留痕" name="comments">
      <el-form label-position="top">
        <el-form-item label="评论内容">
          <el-input
            v-model="contentModel"
            type="textarea"
            :rows="4"
            placeholder="请输入任务评论或协作说明"
          />
        </el-form-item>
        <el-form-item v-if="isManagementRole" label="内部备注">
          <el-switch v-model="internalModel" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="submitting" @click="emit('submit')">
        提交评论
      </el-button>
    </el-collapse-item>
  </el-collapse>

  <template v-else>
    <el-divider>评论与留痕</el-divider>

    <el-form label-position="top">
      <el-form-item label="评论内容">
        <el-input
          v-model="contentModel"
          type="textarea"
          :rows="4"
          placeholder="请输入任务评论或协作说明"
        />
      </el-form-item>
      <el-form-item v-if="isManagementRole" label="内部备注">
        <el-switch v-model="internalModel" />
      </el-form-item>
      <el-form-item label="评论附件">
        <el-upload
          :key="attachmentResetKey"
          :auto-upload="false"
          multiple
          :show-file-list="true"
          :accept="ATTACHMENT_ACCEPT"
          :before-upload="beforeUploadAttachmentFile"
          :on-change="handleFileListChange"
          :on-remove="handleFileListChange"
        >
          <template #trigger>
            <el-button>选择评论附件</el-button>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>

    <el-button type="primary" :loading="submitting" @click="emit('submit')">
      提交评论
    </el-button>
  </template>
</template>

<style scoped>
.comments-collapse {
  margin-top: 16px;
}
</style>
