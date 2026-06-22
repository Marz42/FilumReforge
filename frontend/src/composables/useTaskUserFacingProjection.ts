import type { Task } from '@/types/api'

import { resolveTaskRunLabel } from '@/domain/task-detail/run-label'
import {
  resolveTaskUserFacingStateForTask,
  TASK_USER_FACING_STATE_LABELS,
  userFacingStateTagType,
  type TaskUserFacingState,
} from '@/domain/task-detail/user-state'

export interface TaskCenterWorkspaceRow {
  taskId: string
  title: string
  runLabel: string
  stageLabel: string | null
  userState: TaskUserFacingState
  userStateLabel: string
  userStateTagType: ReturnType<typeof userFacingStateTagType>
  dueDate: string | null
  assigneeId: string | null
  assigneeLabel: string | null
  departmentId: string | null
  relationTypes: string[]
  completedAt: string | null
  isOverdue: boolean
  task: Task
}

export function projectTaskForWorkspace(
  task: Task,
  currentUserId?: string | null,
): TaskCenterWorkspaceRow {
  const userState = resolveTaskUserFacingStateForTask(task, currentUserId)
  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  const dueDate = task.due_date
  const isOverdue =
    dueDate != null
    && task.status !== 'done'
    && new Date(dueDate).getTime() < Date.now()

  return {
    taskId: task.id,
    title: task.title,
    runLabel: resolveTaskRunLabel(task.title, metadata),
    stageLabel: null,
    userState,
    userStateLabel: TASK_USER_FACING_STATE_LABELS[userState],
    userStateTagType: userFacingStateTagType(userState),
    dueDate,
    assigneeId: task.assignee_id,
    assigneeLabel: null,
    departmentId: task.department_id,
    relationTypes: [],
    completedAt: task.completed_at,
    isOverdue,
    task,
  }
}

export function projectTasksForWorkspace(
  tasks: Task[],
  currentUserId?: string | null,
): TaskCenterWorkspaceRow[] {
  return tasks.map((task) => projectTaskForWorkspace(task, currentUserId))
}

export function groupRowsByUserState(
  rows: TaskCenterWorkspaceRow[],
): Record<TaskUserFacingState, TaskCenterWorkspaceRow[]> {
  const grouped: Record<TaskUserFacingState, TaskCenterWorkspaceRow[]> = {
    pending: [],
    in_progress: [],
    awaiting_confirm: [],
    completed: [],
    returned: [],
  }
  for (const row of rows) {
    grouped[row.userState].push(row)
  }
  return grouped
}
