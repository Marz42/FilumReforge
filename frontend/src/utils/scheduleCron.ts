import { HOUR_OPTIONS } from '@/utils/dateTimePicker'

export type ScheduleFrequency = 'daily' | 'weekly' | 'monthly'

export const SCHEDULE_FREQUENCY_OPTIONS: Array<{ value: ScheduleFrequency; label: string }> = [
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
]

export const SCHEDULE_WEEKDAY_OPTIONS = [
  { value: 0, label: '周日' },
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
] as const

export const SCHEDULE_HOUR_OPTIONS = HOUR_OPTIONS

export const SCHEDULE_MINUTE_OPTIONS = Array.from({ length: 60 }, (_, index) =>
  String(index).padStart(2, '0'),
)

export const SCHEDULE_MONTH_DAY_OPTIONS = Array.from({ length: 31 }, (_, index) => {
  const day = index + 1
  return { value: day, label: `${day} 日` }
})

export interface ScheduleCronInput {
  frequency: ScheduleFrequency
  hour: string
  minute: string
  dayOfWeek?: number
  dayOfMonth?: number
}

export function buildCronFromSchedule(input: ScheduleCronInput): string {
  const hour = Number.parseInt(input.hour, 10)
  const minute = Number.parseInt(input.minute, 10)
  if (Number.isNaN(hour) || hour < 0 || hour > 23 || Number.isNaN(minute) || minute < 0 || minute > 59) {
    throw new Error('无效的执行时间')
  }

  switch (input.frequency) {
    case 'daily':
      return `${minute} ${hour} * * *`
    case 'weekly': {
      const dayOfWeek = input.dayOfWeek ?? 1
      if (dayOfWeek < 0 || dayOfWeek > 6) {
        throw new Error('无效的星期')
      }
      return `${minute} ${hour} * * ${dayOfWeek}`
    }
    case 'monthly': {
      const dayOfMonth = input.dayOfMonth ?? 1
      if (dayOfMonth < 1 || dayOfMonth > 31) {
        throw new Error('无效的日期')
      }
      return `${minute} ${hour} ${dayOfMonth} * *`
    }
    default:
      throw new Error('无效的重复周期')
  }
}

export function isScheduleTimeComplete(input: ScheduleCronInput): boolean {
  if (!input.hour || !input.minute) {
    return false
  }
  if (input.frequency === 'weekly' && input.dayOfWeek == null) {
    return false
  }
  if (input.frequency === 'monthly' && input.dayOfMonth == null) {
    return false
  }
  return true
}
