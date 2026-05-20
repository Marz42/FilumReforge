import { fetchAttachmentContent } from '@/api/attachments'
import type { Attachment } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

function revokeLater(url: string, delayMs = 60_000): void {
  window.setTimeout(() => URL.revokeObjectURL(url), delayMs)
}

export async function openAttachmentInline(attachment: Attachment): Promise<void> {
  const blob = await fetchAttachmentContent(attachment.id, 'inline')
  const objectUrl = URL.createObjectURL(blob)
  const opened = window.open(objectUrl, '_blank', 'noopener,noreferrer')
  if (!opened) {
    URL.revokeObjectURL(objectUrl)
    throw new Error('浏览器拦截了弹出窗口，请允许本站弹窗后重试，或改用下载。')
  }
  revokeLater(objectUrl)
}

export async function downloadAttachmentFile(attachment: Attachment): Promise<void> {
  const blob = await fetchAttachmentContent(attachment.id, 'attachment')
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = attachment.original_filename || 'download'
  anchor.rel = 'noopener'
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  revokeLater(objectUrl)
}

export function attachmentActionErrorMessage(error: unknown): string {
  return getErrorMessage(error)
}
