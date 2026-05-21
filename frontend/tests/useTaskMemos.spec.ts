import { describe, expect, it } from 'vitest'

import { memoContentExcerpt, memoDisplayTitle } from '@/composables/useTaskMemos'

describe('useTaskMemos helpers', () => {
  it('uses fallback title when memo title is empty', () => {
    expect(memoDisplayTitle({ title: null })).toBe('无标题')
    expect(memoDisplayTitle({ title: '   ' })).toBe('无标题')
    expect(memoDisplayTitle({ title: '跟进客户' })).toBe('跟进客户')
  })

  it('truncates long memo content for list excerpts', () => {
    const excerpt = memoContentExcerpt('a'.repeat(120), 40)
    expect(excerpt.endsWith('…')).toBe(true)
    expect(excerpt.length).toBe(41)
  })
})
