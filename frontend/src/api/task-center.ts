import type {
  TaskCenterHistoryItem,
  TaskCenterInboxItem,
  TaskCenterPagination,
  TaskCenterSnapshot,
  TaskCenterTrackingItem,
  TaskMemo,
} from '@/types/api'

import { http } from './http'

export interface CreateTaskMemoPayload {
  title?: string | null
  content: string
  related_task_id?: string | null
  is_pinned?: boolean
}

export interface UpdateTaskMemoPayload {
  title?: string | null
  content?: string
  related_task_id?: string | null
  is_pinned?: boolean
}

export interface TaskCenterInboxPage {
  items: TaskCenterInboxItem[]
  pagination: TaskCenterPagination
}

export interface TaskCenterTrackingPage {
  items: TaskCenterTrackingItem[]
  pagination: TaskCenterPagination
}

export interface TaskCenterHistoryPage {
  items: TaskCenterHistoryItem[]
  pagination: TaskCenterPagination
}

export async function getTaskCenterSnapshot(): Promise<TaskCenterSnapshot> {
  const { data } = await http.get<TaskCenterSnapshot>('/task-center')
  return data
}

export async function fetchTaskCenterInboxPage(options?: {
  limit?: number
  cursor?: string | null
}): Promise<TaskCenterInboxPage> {
  const { data } = await http.get<TaskCenterInboxPage>('/task-center/inbox', {
    params: {
      limit: options?.limit,
      cursor: options?.cursor ?? undefined,
    },
  })
  return data
}

export async function fetchTaskCenterTrackingPage(options?: {
  limit?: number
  cursor?: string | null
}): Promise<TaskCenterTrackingPage> {
  const { data } = await http.get<TaskCenterTrackingPage>('/task-center/tracking', {
    params: {
      limit: options?.limit,
      cursor: options?.cursor ?? undefined,
    },
  })
  return data
}

export async function fetchTaskCenterHistoryPage(options?: {
  limit?: number
  cursor?: string | null
}): Promise<TaskCenterHistoryPage> {
  const { data } = await http.get<TaskCenterHistoryPage>('/task-center/history', {
    params: {
      limit: options?.limit,
      cursor: options?.cursor ?? undefined,
    },
  })
  return data
}

export async function createTaskMemo(payload: CreateTaskMemoPayload): Promise<TaskMemo> {
  const { data } = await http.post<TaskMemo>('/task-center/memos', payload)
  return data
}

export async function updateTaskMemo(memoId: string, payload: UpdateTaskMemoPayload): Promise<TaskMemo> {
  const { data } = await http.patch<TaskMemo>(`/task-center/memos/${memoId}`, payload)
  return data
}

export async function deleteTaskMemo(memoId: string): Promise<void> {
  await http.delete(`/task-center/memos/${memoId}`)
}
