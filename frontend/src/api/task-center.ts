import type { TaskCenterSnapshot, TaskMemo } from '@/types/api'

import { http } from './http'

export interface CreateTaskMemoPayload {
  content: string
  related_task_id?: string | null
  is_pinned?: boolean
}

export interface UpdateTaskMemoPayload {
  content?: string
  related_task_id?: string | null
  is_pinned?: boolean
}

export async function getTaskCenterSnapshot(): Promise<TaskCenterSnapshot> {
  const { data } = await http.get<TaskCenterSnapshot>('/task-center')
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
