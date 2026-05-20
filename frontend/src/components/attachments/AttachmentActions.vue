<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { attachmentMimeIsInlineViewable } from '@/constants/attachments'
import type { Attachment } from '@/types/api'
import {
  attachmentActionErrorMessage,
  downloadAttachmentFile,
  openAttachmentInline,
} from '@/utils/attachment-content'

const props = defineProps<{
  attachment: Attachment
  viewTestId?: string
  downloadTestId?: string
}>()

const viewing = ref(false)
const downloading = ref(false)

const canView = () => attachmentMimeIsInlineViewable(props.attachment.mime_type)

async function handleView(): Promise<void> {
  viewing.value = true
  try {
    await openAttachmentInline(props.attachment)
  } catch (error) {
    ElMessage.error(attachmentActionErrorMessage(error))
  } finally {
    viewing.value = false
  }
}

async function handleDownload(): Promise<void> {
  downloading.value = true
  try {
    await downloadAttachmentFile(props.attachment)
  } catch (error) {
    ElMessage.error(attachmentActionErrorMessage(error))
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <el-space>
    <el-button
      v-if="canView()"
      link
      type="primary"
      :loading="viewing"
      :data-testid="viewTestId"
      @click="handleView"
    >
      查看
    </el-button>
    <el-button
      link
      type="primary"
      :loading="downloading"
      :data-testid="downloadTestId"
      @click="handleDownload"
    >
      {{ canView() ? '下载' : '下载' }}
    </el-button>
  </el-space>
</template>
