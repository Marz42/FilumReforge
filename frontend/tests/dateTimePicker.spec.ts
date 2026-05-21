import { describe, expect, it } from 'vitest'

import { mergeDateAndTime, parseDateTimeParts, roundToFiveMinutes } from '@/utils/dateTimePicker'

describe('dateTimePicker utils', () => {
  it('rounds minutes up to the next five-minute step', () => {
    const value = new Date(2025, 0, 2, 10, 7, 30)
    const rounded = roundToFiveMinutes(value)
    expect(rounded.getMinutes()).toBe(10)
    expect(rounded.getSeconds()).toBe(0)
  })

  it('merges date, hour, and minute into a rounded datetime', () => {
    const merged = mergeDateAndTime('2025-01-02', '10', '07')
    expect(merged).not.toBeNull()
    const parts = parseDateTimeParts(merged)
    expect(parts.hour).toBe('10')
    expect(parts.minute).toBe('10')
  })

  it('returns empty parts for null values', () => {
    expect(parseDateTimeParts(null)).toEqual({ date: '', hour: '', minute: '' })
  })
})
