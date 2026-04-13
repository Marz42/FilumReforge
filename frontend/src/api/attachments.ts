import type { Attachment, AttachmentTargetType, AttachmentVisibility } from '@/types/api'
import { http } from './http'

export interface ListAttachmentsPayload {
  target_type: AttachmentTargetType
  target_id: string
}

export interface UploadAttachmentPayload extends ListAttachmentsPayload {
  file: File
  visibility?: AttachmentVisibility
  relation?: string
}

export async function listAttachments(payload: ListAttachmentsPayload): Promise<Attachment[]> {
  const { data } = await http.get<Attachment[]>('/attachments', {
    params: payload,
  })
  return data
}

export async function uploadAttachment(payload: UploadAttachmentPayload): Promise<Attachment> {
  const formData = new FormData()
  formData.append('file', payload.file)
  formData.append('target_type', payload.target_type)
  formData.append('target_id', payload.target_id)
  formData.append('visibility', payload.visibility ?? 'private')
  formData.append('relation', payload.relation ?? 'primary')

  const { data } = await http.post<Attachment>('/attachments', formData)
  return data
}
