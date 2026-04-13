import type { Task, TaskPriority } from '@/types/api'
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

export async function listTasks(): Promise<Task[]> {
  const { data } = await http.get<Task[]>('/tasks')
  return data
}

export async function createTask(payload: CreateTaskPayload): Promise<Task> {
  const { data } = await http.post<Task>('/tasks', payload)
  return data
}
