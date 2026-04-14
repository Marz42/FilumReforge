import type {
  CommentFormat,
  Task,
  TaskActivityEntry,
  TaskBoardColumn,
  TaskComment,
  TaskGanttEntry,
  TaskPriority,
  TaskStatsSummary,
  TaskStatus,
  TaskWatcher,
  TaskWorkloadRow,
} from '@/types/api'
import { http } from './http'

export interface CreateTaskPayload {
  title: string
  assignee_id: string
  description?: string | null
  department_id?: string | null
  due_date?: string | null
  priority?: TaskPriority
  dependency_ids?: string[]
}

export interface CreateTaskCommentPayload {
  content: string
  content_format?: CommentFormat
  is_internal?: boolean
  files?: File[]
}

export async function listTasks(): Promise<Task[]> {
  const { data } = await http.get<Task[]>('/tasks')
  return data
}

export async function listTaskBoard(): Promise<TaskBoardColumn[]> {
  const { data } = await http.get<TaskBoardColumn[]>('/tasks/views/board')
  return data
}

export async function listTaskGantt(): Promise<TaskGanttEntry[]> {
  const { data } = await http.get<TaskGanttEntry[]>('/tasks/views/gantt')
  return data
}

export async function createTask(payload: CreateTaskPayload): Promise<Task> {
  const { data } = await http.post<Task>('/tasks', payload)
  return data
}

export async function updateTaskStatus(taskId: string, status: TaskStatus): Promise<Task> {
  const { data } = await http.patch<Task>(`/tasks/${taskId}/status`, { status })
  return data
}

export async function listTaskComments(taskId: string): Promise<TaskComment[]> {
  const { data } = await http.get<TaskComment[]>(`/tasks/${taskId}/comments`)
  return data
}

export async function createTaskComment(
  taskId: string,
  payload: CreateTaskCommentPayload,
): Promise<TaskComment> {
  const formData = new FormData()
  formData.append('content', payload.content)
  formData.append('content_format', payload.content_format ?? 'markdown')
  formData.append('is_internal', payload.is_internal ? 'true' : 'false')
  for (const file of payload.files ?? []) {
    formData.append('files', file)
  }

  const { data } = await http.post<TaskComment>(`/tasks/${taskId}/comments`, formData)
  return data
}

export async function listTaskActivity(taskId: string): Promise<TaskActivityEntry[]> {
  const { data } = await http.get<TaskActivityEntry[]>(`/tasks/${taskId}/activity`)
  return data
}

export async function getTaskStatsSummary(): Promise<TaskStatsSummary> {
  const { data } = await http.get<TaskStatsSummary>('/tasks/stats/summary')
  return data
}

export async function getTaskWorkload(): Promise<TaskWorkloadRow[]> {
  const { data } = await http.get<TaskWorkloadRow[]>('/tasks/stats/workload')
  return data
}

export async function listTaskWatchers(taskId: string): Promise<TaskWatcher[]> {
  const { data } = await http.get<TaskWatcher[]>(`/tasks/${taskId}/watchers`)
  return data
}

export async function addTaskWatchers(taskId: string, userIds: string[]): Promise<TaskWatcher[]> {
  const { data } = await http.post<TaskWatcher[]>(`/tasks/${taskId}/watchers`, {
    user_ids: userIds,
  })
  return data
}
