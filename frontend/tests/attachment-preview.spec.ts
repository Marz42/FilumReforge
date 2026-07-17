import readXlsxFile from 'read-excel-file/browser'
import { describe, expect, it, vi } from 'vitest'

import {
  attachmentMimeIsInlineViewable,
  attachmentSupportsPreview,
  resolveAttachmentPreviewKind,
} from '@/constants/attachments'
import { buildAttachmentPreviewContent } from '@/utils/attachment-preview'

vi.mock('read-excel-file/browser', () => ({
  default: vi.fn(),
}))

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
  it('renders markdown to sanitized html', async () => {
    const blob = new Blob(['# Title\n\nBody'], { type: 'text/markdown' })
    const result = await buildAttachmentPreviewContent(blob, 'text/markdown')
    expect(result.content.kind).toBe('markdown')
    if (result.content.kind === 'markdown') {
      expect(result.content.html).toContain('<h1')
      expect(result.content.html).toContain('Body')
    }
  })

  it('sanitizes xss payloads in markdown previews', async () => {
    const blob = new Blob(
      ['# Safe\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[x](javascript:alert(1))'],
      { type: 'text/markdown' },
    )
    const result = await buildAttachmentPreviewContent(blob, 'text/markdown')
    expect(result.content.kind).toBe('markdown')
    if (result.content.kind === 'markdown') {
      expect(result.content.html).toContain('Safe')
      expect(result.content.html).not.toMatch(/<script/i)
      expect(result.content.html).not.toMatch(/onerror/i)
      expect(result.content.html).not.toMatch(/javascript:/i)
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

  it('parses xlsx cells as escaped template data and caps oversized previews', async () => {
    vi.mocked(readXlsxFile).mockResolvedValueOnce([
      {
        sheet: 'Sheet 1',
        data: [
          ['Name', 'Value'],
          ['<img src=x onerror=alert(1)>', 42],
          [true, null],
        ],
      },
      {
        sheet: 'Wide',
        data: [Array.from({ length: 101 }, (_, index) => index)],
      },
    ])

    const blob = new Blob(['xlsx'], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const result = await buildAttachmentPreviewContent(blob, blob.type)

    expect(result.content.kind).toBe('xlsx')
    if (result.content.kind === 'xlsx') {
      expect(result.content.sheets[0]?.rows[1]).toEqual(['<img src=x onerror=alert(1)>', '42'])
      expect(result.content.sheets[0]?.truncated).toBe(false)
      expect(result.content.sheets[1]?.rows[0]).toHaveLength(100)
      expect(result.content.sheets[1]?.truncated).toBe(true)
    }
  })
})
