import { ref } from 'vue'

import type { Attachment } from '@/types/api'
import {
  loadAttachmentPreview,
  revokeAttachmentPreviewUrls,
  type AttachmentPreviewContent,
} from '@/utils/attachment-preview'

const visible = ref(false)
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const activeAttachment = ref<Attachment | null>(null)
const previewContent = ref<AttachmentPreviewContent | null>(null)
const activeObjectUrls = ref<string[]>([])

function resetPreviewState(): void {
  revokeAttachmentPreviewUrls(activeObjectUrls.value)
  activeObjectUrls.value = []
  previewContent.value = null
  errorMessage.value = null
  activeAttachment.value = null
}

function closeAttachmentPreview(): void {
  visible.value = false
  resetPreviewState()
}

async function openAttachmentPreview(attachment: Attachment): Promise<void> {
  resetPreviewState()
  activeAttachment.value = attachment
  visible.value = true
  loading.value = true
  try {
    const result = await loadAttachmentPreview(attachment)
    activeObjectUrls.value = result.objectUrls
    previewContent.value = result.content
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '附件预览失败，请稍后重试或下载查看。'
  } finally {
    loading.value = false
  }
}

export function useAttachmentPreview() {
  return {
    visible,
    loading,
    errorMessage,
    activeAttachment,
    previewContent,
    openAttachmentPreview,
    closeAttachmentPreview,
  }
}
