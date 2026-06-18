import { describe, expect, it } from 'vitest'

import { resolveRunColor } from '@/constants/task-center-run-colors'

describe('task-center-run-colors', () => {
  it('returns stable color for the same run label', () => {
    expect(resolveRunColor('Batch-A')).toBe(resolveRunColor('Batch-A'))
  })

  it('returns palette color for empty label', () => {
    expect(resolveRunColor('')).toMatch(/^#[0-9a-f]{6}$/i)
  })
})
