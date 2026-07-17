import { describe, expect, it } from 'vitest'

import { renderSafeMarkdown, sanitizeHtml } from '@/utils/safe-markdown'

describe('renderSafeMarkdown', () => {
  it('renders headings, lists, tables and code blocks', () => {
    const html = renderSafeMarkdown(
      [
        '# Title',
        '',
        '- item',
        '',
        '| A | B |',
        '| --- | --- |',
        '| 1 | 2 |',
        '',
        '```',
        'const x = 1',
        '```',
      ].join('\n'),
    )
    expect(html).toContain('<h1')
    expect(html).toContain('<li>')
    expect(html).toContain('<table>')
    expect(html).toContain('<code>')
    expect(html).toContain('Title')
  })

  it('strips script tags', () => {
    const html = renderSafeMarkdown('Hello <script>alert(1)</script> world')
    expect(html).not.toMatch(/<script/i)
    expect(html).not.toContain('alert(1)')
    expect(html).toContain('Hello')
    expect(html).toContain('world')
  })

  it('strips onerror handlers from images', () => {
    const html = renderSafeMarkdown('<img src=x onerror=alert(1)>')
    expect(html).not.toMatch(/onerror/i)
    expect(html).not.toContain('alert(1)')
  })

  it('removes javascript: links', () => {
    const html = renderSafeMarkdown('[click](javascript:alert(1))')
    expect(html).not.toMatch(/javascript:/i)
    expect(html).not.toContain('alert(1)')
  })

  it('removes iframe tags', () => {
    const html = renderSafeMarkdown('<iframe src="https://evil.example"></iframe>safe')
    expect(html).not.toMatch(/<iframe/i)
    expect(html).toContain('safe')
  })

  it('forces external links to open safely', () => {
    const html = renderSafeMarkdown('[docs](https://example.com/path)')
    expect(html).toContain('href="https://example.com/path"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })
})

describe('sanitizeHtml', () => {
  it('sanitizes mammoth-style HTML payloads', () => {
    const html = sanitizeHtml('<p>ok</p><img src=x onerror=alert(1)><script>bad()</script>')
    expect(html).toContain('<p>ok</p>')
    expect(html).not.toMatch(/onerror/i)
    expect(html).not.toMatch(/<script/i)
  })
})
