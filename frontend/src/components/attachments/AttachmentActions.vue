<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { attachmentSupportsPreview } from '@/constants/attachments'
import { useAttachmentPreview } from '@/composables/useAttachmentPreview'
import type { Attachment } from '@/types/api'
import {
  attachmentActionErrorMessage,
  downloadAttachmentFile,
} from '@/utils/attachment-content'

const props = defineProps<{
  attachment: Attachment
  viewTestId?: string
  downloadTestId?: string
}>()

const viewing = ref(false)
const downloading = ref(false)
const { openAttachmentPreview } = useAttachmentPreview()

const canPreview = () => attachmentSupportsPreview(props.attachment.mime_type)

async function handleView(): Promise<void> {
  viewing.value = true
  try {
    await openAttachmentPreview(props.attachment)
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
      v-if="canPreview()"
      link
      type="primary"
      :loading="viewing"
      :data-testid="viewTestId"
      @click="handleView"
    >
      预览
    </el-button>
    <el-button
      link
      type="primary"
      :loading="downloading"
      :data-testid="downloadTestId"
      @click="handleDownload"
    >
      下载
    </el-button>
  </el-space>
</template>
