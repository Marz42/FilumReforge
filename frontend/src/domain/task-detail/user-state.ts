import type { Task, TaskStatus } from '@/types/api'

import { resolveTaskDetailProfile, type TaskDetailProfileId } from './profile'

export type TaskUserFacingState =
  | 'pending'
  | 'in_progress'
  | 'awaiting_confirm'
  | 'completed'
  | 'returned'

export const TASK_USER_FACING_STATE_LABELS: Record<TaskUserFacingState, string> = {
  pending: '待处理',
  in_progress: '进行中',
  awaiting_confirm: '待确认',
  completed: '已完成',
  returned: '已退回',
}

function readMetadata(task: Task): Record<string, unknown> {
  return (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
}

function hasReworkSignal(metadata: Record<string, unknown>): boolean {
  const captureState = metadata.latest_capture_state
  if (captureState === 'rejected' || captureState === 'returned') {
    return true
  }
  const reworkReason = metadata.latest_rework_reason
  return typeof reworkReason === 'string' && reworkReason.trim().length > 0
    && metadata.latest_handshake_action !== 'assigned'
}

export function resolveTaskUserFacingState(
  task: Task,
  profileId: TaskDetailProfileId,
): TaskUserFacingState {
  const metadata = readMetadata(task)

  if (hasReworkSignal(metadata) && task.status !== 'done') {
    return 'returned'
  }

  if (task.status === 'done') {
    return 'completed'
  }

  if (profileId === 'video_batch_root') {
    return 'in_progress'
  }

  if (profileId === 'video_n1_capture' || profileId === 'video_n2_aggregate') {
    if (task.status === 'todo' || task.status === 'doing') {
      return 'pending'
    }
    if (task.status === 'review') {
      return profileId === 'video_n2_aggregate' ? 'pending' : 'completed'
    }
  }

  if (profileId === 'video_production_step') {
    if (task.status === 'review') {
      return 'awaiting_confirm'
    }
    if (task.status === 'todo' || task.status === 'doing') {
      return 'pending'
    }
  }

  return mapTaskStatusFallback(task.status)
}

export function resolveTaskUserFacingStateForTask(
  task: Task,
  currentUserId?: string | null,
): TaskUserFacingState {
  const profile = resolveTaskDetailProfile(task, { currentUserId })
  return resolveTaskUserFacingState(task, profile.id)
}

function mapTaskStatusFallback(status: TaskStatus): TaskUserFacingState {
  if (status === 'done') {
    return 'completed'
  }
  if (status === 'review') {
    return 'awaiting_confirm'
  }
  if (status === 'doing') {
    return 'in_progress'
  }
  return 'pending'
}

export function userFacingStateTagType(
  state: TaskUserFacingState,
): '' | 'info' | 'warning' | 'success' | 'danger' {
  switch (state) {
    case 'pending':
      return 'warning'
    case 'in_progress':
      return 'info'
    case 'awaiting_confirm':
      return 'info'
    case 'completed':
      return 'success'
    case 'returned':
      return 'danger'
    default:
      return 'info'
  }
}
