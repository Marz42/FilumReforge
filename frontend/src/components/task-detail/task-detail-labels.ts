import type { TaskPriority, TaskStatus } from '@/types/api'

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待办',
  doing: '进行中',
  review: '评审中',
  blocked: '已阻塞',
  done: '已完成',
}

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: '低',
  medium: '中',
  high: '高',
  urgent: '紧急',
}

export const STATUS_TAG_TYPES: Record<TaskStatus, '' | 'info' | 'warning' | 'success'> = {
  todo: 'info',
  doing: 'warning',
  review: '',
  blocked: 'warning',
  done: 'success',
}

export const PRIORITY_TAG_TYPES: Record<TaskPriority, '' | 'info' | 'warning' | 'danger'> = {
  low: 'info',
  medium: '',
  high: 'warning',
  urgent: 'danger',
}

export type TagTypeInput = '' | 'info' | 'warning' | 'success' | 'danger' | 'primary'

export type TagTypeOutput = 'info' | 'warning' | 'success' | 'danger' | 'primary' | undefined

export function normalizeTagType(value: TagTypeInput): TagTypeOutput {
  return value || undefined
}

export function resolveStatusLabel(status: TaskStatus): string {
  return STATUS_LABELS[status]
}

export function resolvePriorityLabel(priority: TaskPriority): string {
  return PRIORITY_LABELS[priority]
}
