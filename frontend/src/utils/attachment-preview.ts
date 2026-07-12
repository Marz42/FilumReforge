import mammoth from 'mammoth'
import { marked } from 'marked'
import readXlsxFile, { type CellValue } from 'read-excel-file/browser'

import { fetchAttachmentContent } from '@/api/attachments'
import { resolveAttachmentPreviewKind } from '@/constants/attachments'
import type { Attachment } from '@/types/api'

export type AttachmentPreviewSheet = {
  name: string
  rows: string[][]
  truncated: boolean
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

const XLSX_PREVIEW_MAX_ROWS = 500
const XLSX_PREVIEW_MAX_COLUMNS = 100

function formatSpreadsheetCell(value: CellValue | null): string {
  if (value == null) {
    return ''
  }
  if (value instanceof Date) {
    return value.toLocaleString()
  }
  return String(value)
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
      const workbook = await readXlsxFile(blob)
      const sheets = workbook.map(({ sheet, data }) => ({
        name: sheet,
        rows: data
          .slice(0, XLSX_PREVIEW_MAX_ROWS)
          .map((row) => row.slice(0, XLSX_PREVIEW_MAX_COLUMNS).map(formatSpreadsheetCell)),
        truncated:
          data.length > XLSX_PREVIEW_MAX_ROWS ||
          data.some((row) => row.length > XLSX_PREVIEW_MAX_COLUMNS),
      }))
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
