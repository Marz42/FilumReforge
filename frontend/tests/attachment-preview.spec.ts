import { describe, expect, it } from 'vitest'

import {
  attachmentMimeIsInlineViewable,
  attachmentSupportsPreview,
  resolveAttachmentPreviewKind,
} from '@/constants/attachments'
import { buildAttachmentPreviewContent } from '@/utils/attachment-preview'

describe('attachment preview kinds', () => {
  it('maps supported mime types to preview kinds', () => {
    expect(resolveAttachmentPreviewKind('image/png')).toBe('image')
    expect(resolveAttachmentPreviewKind('application/pdf')).toBe('pdf')
    expect(resolveAttachmentPreviewKind('text/plain')).toBe('text')
    expect(resolveAttachmentPreviewKind('text/markdown')).toBe('markdown')
    expect(
      resolveAttachmentPreviewKind(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      ),
    ).toBe('docx')
    expect(
      resolveAttachmentPreviewKind(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      ),
    ).toBe('xlsx')
    expect(resolveAttachmentPreviewKind('audio/wav')).toBe('audio')
    expect(resolveAttachmentPreviewKind('audio/mpeg')).toBe('audio')
    expect(resolveAttachmentPreviewKind('application/octet-stream')).toBeNull()
  })

  it('treats inline viewable types as previewable', () => {
    expect(attachmentSupportsPreview('text/markdown')).toBe(true)
    expect(attachmentMimeIsInlineViewable('text/markdown')).toBe(true)
  })
})

describe('buildAttachmentPreviewContent', () => {
  it('renders markdown to html', async () => {
    const blob = new Blob(['# Title\n\nBody'], { type: 'text/markdown' })
    const result = await buildAttachmentPreviewContent(blob, 'text/markdown')
    expect(result.content.kind).toBe('markdown')
    if (result.content.kind === 'markdown') {
      expect(result.content.html).toContain('<h1')
      expect(result.content.html).toContain('Body')
    }
  })

  it('creates audio preview url', async () => {
    const blob = new Blob(['RIFF----WAVE'], { type: 'audio/wav' })
    const result = await buildAttachmentPreviewContent(blob, 'audio/wav')
    expect(result.content.kind).toBe('audio')
    expect(result.objectUrls).toHaveLength(1)
    if (result.content.kind === 'audio') {
      expect(result.content.mime).toBe('audio/wav')
      URL.revokeObjectURL(result.content.url)
    }
  })
})
