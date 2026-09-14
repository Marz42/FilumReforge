import { describe, expect, it } from 'vitest'

import {
  extraRecordKeys,
  formatRecordValue,
  parseRecordObject,
  parseRecordValue,
} from '@/utils/recordFields'

describe('recordFields', () => {
  it('round-trips unknown object and array values', () => {
    expect(parseRecordValue(formatRecordValue({ skills: ['qa'] }))).toEqual({ skills: ['qa'] })
    expect(parseRecordValue(formatRecordValue(['python']))).toEqual(['python'])
  })

  it('parses numbers and keeps invalid numeric text', () => {
    expect(parseRecordValue('12.5', 'number')).toBe(12.5)
    expect(parseRecordValue('n/a', 'number')).toBe('n/a')
  })

  it('keeps extra keys that are not in field definitions', () => {
    expect(
      extraRecordKeys(
        { skills: ['python'], salary: 1 },
        [{ field_key: 'salary', label: '薪资', field_type: 'number', storage_target: 'custom' }],
        'custom',
      ),
    ).toEqual(['skills'])
  })

  it('rejects non-object JSON payloads', () => {
    expect(() => parseRecordObject('[]')).toThrow()
    expect(parseRecordObject('{"band":"P5"}')).toEqual({ band: 'P5' })
  })
})
