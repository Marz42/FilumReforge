import mammoth from 'mammoth'
import { marked } from 'marked'
import * as XLSX from 'xlsx'

import { fetchAttachmentContent } from '@/api/attachments'
import { resolveAttachmentPreviewKind } from '@/constants/attachments'
import type { Attachment } from '@/types/api'

export type AttachmentPreviewSheet = {
  name: string
  html: string
}

export type AttachmentPreviewContent =
  | { kind: 'image'; url: string }
  | { kind: 'pdf'; url: string }
  | { kind: 'text'; text: string }
  | { kind: 'markdown'; html: string }
  | { kind: 'docx'; html: string }
  | { kind: 'xlsx'; sheets: AttachmentPreviewSheet[] }
  | { kind: 'audio'; url: string; mime: string }

export type AttachmentPreviewLoadResult = {
  content: AttachmentPreviewContent
  objectUrls: string[]
}

function normalizeAudioMime(mime: string): string {
  const normalized = mime.split(';')[0]?.trim().toLowerCase() ?? ''
  return normalized === 'audio/x-wav' ? 'audio/wav' : normalized
}

async function blobToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return blob.arrayBuffer()
}

export async function buildAttachmentPreviewContent(
  blob: Blob,
  mime: string,
): Promise<AttachmentPreviewLoadResult> {
  const kind = resolveAttachmentPreviewKind(mime)
  if (!kind) {
    throw new Error('该附件类型暂不支持预览。')
  }

  const objectUrls: string[] = []
  const trackUrl = (url: string): string => {
    objectUrls.push(url)
    return url
  }

  switch (kind) {
    case 'image':
      return {
        content: { kind: 'image', url: trackUrl(URL.createObjectURL(blob)) },
        objectUrls,
      }
    case 'pdf':
      return {
        content: { kind: 'pdf', url: trackUrl(URL.createObjectURL(blob)) },
        objectUrls,
      }
    case 'text':
      return {
        content: { kind: 'text', text: await blob.text() },
        objectUrls,
      }
    case 'markdown': {
      const text = await blob.text()
      const html = await marked.parse(text)
      return {
        content: { kind: 'markdown', html: String(html) },
        objectUrls,
      }
    }
    case 'docx': {
      const arrayBuffer = await blobToArrayBuffer(blob)
      const result = await mammoth.convertToHtml({ arrayBuffer })
      return {
        content: { kind: 'docx', html: result.value },
        objectUrls,
      }
    }
    case 'xlsx': {
      const arrayBuffer = await blobToArrayBuffer(blob)
      const workbook = XLSX.read(arrayBuffer, { type: 'array' })
      const sheets = workbook.SheetNames.map((name) => {
        const sheet = workbook.Sheets[name]
        return {
          name,
          html: sheet ? XLSX.utils.sheet_to_html(sheet) : '<table></table>',
        }
      })
      return {
        content: { kind: 'xlsx', sheets },
        objectUrls,
      }
    }
    case 'audio':
      return {
        content: {
          kind: 'audio',
          url: trackUrl(URL.createObjectURL(blob)),
          mime: normalizeAudioMime(mime),
        },
        objectUrls,
      }
    default:
      throw new Error('该附件类型暂不支持预览。')
  }
}

export async function loadAttachmentPreview(attachment: Attachment): Promise<AttachmentPreviewLoadResult> {
  const blob = await fetchAttachmentContent(attachment.id, 'inline')
  return buildAttachmentPreviewContent(blob, attachment.mime_type)
}

export function revokeAttachmentPreviewUrls(urls: string[]): void {
  for (const url of urls) {
    URL.revokeObjectURL(url)
  }
}
