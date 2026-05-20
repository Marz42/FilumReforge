import type { Attachment, AttachmentTargetType, AttachmentVisibility } from '@/types/api'
import { http } from './http'

export interface ListAttachmentsPayload {
  target_type: AttachmentTargetType
  target_id: string
}

export interface UploadAttachmentPayload {
  file: File
  target_type?: AttachmentTargetType
  target_id?: string
  visibility?: AttachmentVisibility
  relation?: string
}

export async function listAttachments(payload: ListAttachmentsPayload): Promise<Attachment[]> {
  const { data } = await http.get<Attachment[]>('/attachments', {
    params: payload,
  })
  return data
}

export type AttachmentContentDisposition = 'inline' | 'attachment'

export async function fetchAttachmentContent(
  attachmentId: string,
  disposition: AttachmentContentDisposition = 'attachment',
): Promise<Blob> {
  const { data } = await http.get<Blob>(`/attachments/${attachmentId}/content`, {
    params: { disposition },
    responseType: 'blob',
  })
  return data
}

export async function uploadAttachment(payload: UploadAttachmentPayload): Promise<Attachment> {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.target_type != null && payload.target_id != null) {
    formData.append('target_type', payload.target_type)
    formData.append('target_id', payload.target_id)
  }
  formData.append('visibility', payload.visibility ?? 'private')
  formData.append('relation', payload.relation ?? 'primary')

  const { data } = await http.post<Attachment>('/attachments', formData)
  return data
}
