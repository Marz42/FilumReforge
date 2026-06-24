import { describe, expect, it } from 'vitest'

import { buildCronFromSchedule } from '@/utils/scheduleCron'

describe('buildCronFromSchedule', () => {
  it('builds daily cron', () => {
    expect(
      buildCronFromSchedule({ frequency: 'daily', hour: '09', minute: '30' }),
    ).toBe('30 9 * * *')
  })

  it('builds weekly cron', () => {
    expect(
      buildCronFromSchedule({ frequency: 'weekly', hour: '09', minute: '00', dayOfWeek: 1 }),
    ).toBe('0 9 * * 1')
  })

  it('builds monthly cron', () => {
    expect(
      buildCronFromSchedule({ frequency: 'monthly', hour: '17', minute: '00', dayOfMonth: 1 }),
    ).toBe('0 17 1 * *')
  })
})
