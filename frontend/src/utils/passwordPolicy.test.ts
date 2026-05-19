import { describe, expect, it } from 'vitest'

import {
  formatPasswordValidationMessage,
  PASSWORD_POLICY_FALLBACK,
  validatePasswordClient,
} from '@/utils/passwordPolicy'

describe('validatePasswordClient', () => {
  it('accepts passwords that meet backend policy', () => {
    const result = validatePasswordClient('StrongPassword123!')
    expect(result.valid).toBe(true)
    expect(result.reasons).toEqual([])
  })

  it('rejects short passwords with readable reasons', () => {
    const result = validatePasswordClient('Ab1!')
    expect(result.valid).toBe(false)
    expect(result.reasons.some((reason) => reason.includes('至少'))).toBe(true)
  })

  it('rejects passwords missing enough character categories', () => {
    const result = validatePasswordClient('12345678')
    expect(result.valid).toBe(false)
    expect(result.reasons.some((reason) => reason.includes('三类'))).toBe(true)
  })

  it('formats validation messages for UI display', () => {
    const result = validatePasswordClient('abcdefgh')
    expect(formatPasswordValidationMessage(result.reasons)).toContain('三类')
    expect(formatPasswordValidationMessage([])).toBe(PASSWORD_POLICY_FALLBACK)
  })
})
