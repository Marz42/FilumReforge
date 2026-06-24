/** 与后端 `AttachmentService` 白名单与大小上限对齐（文案以后端校验为准）。 */

export const ATTACHMENT_ACCEPT =
  '.png,.jpg,.jpeg,.gif,.webp,.pdf,.xlsx,.txt,.md,.docx,.mp3,.wav,image/png,image/jpeg,image/gif,image/webp,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,audio/mpeg,audio/wav,audio/x-wav'

const TEXT_CLASS_MAX = 10 * 1024 * 1024
const AUDIO_MAX = 50 * 1024 * 1024
const OTHER_MAX = 25 * 1024 * 1024

const EXT_ALLOWED = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.pdf',
  '.xlsx',
  '.txt',
  '.md',
  '.docx',
  '.mp3',
  '.wav',
])

const MIME_TEXT_CLASS = new Set(['text/plain', 'text/markdown', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'])
const MIME_AUDIO = new Set(['audio/mpeg', 'audio/wav', 'audio/x-wav'])

function extensionOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

function maxBytesForMime(mime: string): number {
  const m = mime.split(';')[0]?.trim().toLowerCase() ?? ''
  const norm = m === 'audio/x-wav' ? 'audio/wav' : m
  if (MIME_TEXT_CLASS.has(norm)) {
    return TEXT_CLASS_MAX
  }
  if (MIME_AUDIO.has(norm)) {
    return AUDIO_MAX
  }
  return OTHER_MAX
}

const MIME_BY_EXT: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.pdf': 'application/pdf',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
}

/** 返回错误文案；通过则返回 null */
export function validateAttachmentFile(file: File): string | null {
  const ext = extensionOf(file.name)
  if (!EXT_ALLOWED.has(ext)) {
    return '仅支持图片、PDF、Excel（.xlsx）、文本（.txt/.md）、Word（.docx）与音频（.mp3/.wav）。'
  }
  const rawType = (file.type || '').split(';')[0]?.trim().toLowerCase() ?? ''
  const inferred = MIME_BY_EXT[ext] ?? ''
  const effective = (rawType === 'audio/x-wav' ? 'audio/wav' : rawType) || inferred
  if (rawType) {
    const allowedMimeByExt: Record<string, Set<string>> = {
      '.png': new Set(['image/png']),
      '.jpg': new Set(['image/jpeg']),
      '.jpeg': new Set(['image/jpeg']),
      '.gif': new Set(['image/gif']),
      '.webp': new Set(['image/webp']),
      '.pdf': new Set(['application/pdf']),
      '.xlsx': new Set(['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']),
      '.txt': new Set(['text/plain']),
      '.md': new Set(['text/markdown', 'text/plain']),
      '.docx': new Set(['application/vnd.openxmlformats-officedocument.wordprocessingml.document']),
      '.mp3': new Set(['audio/mpeg']),
      '.wav': new Set(['audio/wav', 'audio/x-wav']),
    }
    const allowed = allowedMimeByExt[ext]
    const declared = rawType === 'audio/x-wav' ? 'audio/wav' : rawType
    if (allowed && !allowed.has(rawType) && !allowed.has(declared)) {
      return '文件扩展名与浏览器声明的类型不一致，请重选文件或换用其他浏览器。'
    }
  }
  const limit = maxBytesForMime(effective)
  if (file.size > limit) {
    if (limit === TEXT_CLASS_MAX) {
      return '文本类附件（含 .txt / .md / .docx）单文件不能超过 10MB。'
    }
    if (limit === AUDIO_MAX) {
      return '音频附件（.mp3 / .wav）单文件不能超过 50MB。'
    }
    return '该附件类型单文件不能超过 25MB（图片 / PDF / Excel）。'
  }
  return null
}

export function attachmentMimeIsInlineViewable(mime: string): boolean {
  return resolveAttachmentPreviewKind(mime) !== null
}

export type AttachmentPreviewKind = 'image' | 'pdf' | 'text' | 'markdown' | 'docx' | 'xlsx' | 'audio'

export function resolveAttachmentPreviewKind(mime: string): AttachmentPreviewKind | null {
  const normalized = mime.split(';')[0]?.trim().toLowerCase() ?? ''
  if (normalized === 'application/pdf') {
    return 'pdf'
  }
  if (normalized.startsWith('image/')) {
    return 'image'
  }
  if (normalized === 'text/plain') {
    return 'text'
  }
  if (normalized === 'text/markdown') {
    return 'markdown'
  }
  if (normalized === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
    return 'docx'
  }
  if (normalized === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
    return 'xlsx'
  }
  if (normalized === 'audio/mpeg' || normalized === 'audio/wav' || normalized === 'audio/x-wav') {
    return 'audio'
  }
  return null
}

export function attachmentSupportsPreview(mime: string): boolean {
  return resolveAttachmentPreviewKind(mime) !== null
}
