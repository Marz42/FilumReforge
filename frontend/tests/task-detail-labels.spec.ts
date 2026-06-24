import { describe, expect, it } from 'vitest'

import {
  normalizeTagType,
  resolvePriorityLabel,
  resolveStatusLabel,
} from '@/components/task-detail/task-detail-labels'

describe('task-detail-labels', () => {
  it('maps task status and priority labels', () => {
    expect(resolveStatusLabel('review')).toBe('评审中')
    expect(resolvePriorityLabel('urgent')).toBe('紧急')
    expect(normalizeTagType('')).toBeUndefined()
    expect(normalizeTagType('success')).toBe('success')
  })
})
