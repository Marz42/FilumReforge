import type {
  TaskSchedule,
  TaskTemplate,
  TaskTemplateInstance,
  TaskTemplateInstantiation,
} from '@/types/api'
import { http } from './http'

export interface TaskTemplateStepPayload {
  step_key: string
  title: string
  description?: string | null
  step_type?: string
  assignment_mode?: string
  join_mode?: string
  default_assignee_rule?: Record<string, unknown>
  default_due_offset_hours?: number | null
  sort_order?: number | null
  config?: Record<string, unknown>
  depends_on_step_keys?: string[]
}

export interface CreateTaskTemplatePayload {
  code: string
  name: string
  category: string
  description?: string | null
  trigger_type?: string
  config?: Record<string, unknown>
  is_active?: boolean
  steps: TaskTemplateStepPayload[]
}

export type UpdateTaskTemplatePayload = Partial<CreateTaskTemplatePayload>

export interface InstantiateTaskTemplatePayload {
  department_id?: string | null
  watcher_user_ids?: string[]
  payload?: Record<string, unknown>
}

export interface CreateTaskSchedulePayload {
  template_id: string
  cron_expr: string
  timezone?: string
  payload?: Record<string, unknown>
  is_active?: boolean
}

export interface UpdateTaskSchedulePayload {
  cron_expr?: string
  timezone?: string
  payload?: Record<string, unknown>
  is_active?: boolean
}

export async function listTaskTemplates(): Promise<TaskTemplate[]> {
  const { data } = await http.get<TaskTemplate[]>('/task-templates')
  return data
}

export async function createTaskTemplate(payload: CreateTaskTemplatePayload): Promise<TaskTemplate> {
  const { data } = await http.post<TaskTemplate>('/task-templates', payload)
  return data
}

export async function updateTaskTemplate(
  templateId: string,
  payload: UpdateTaskTemplatePayload,
): Promise<TaskTemplate> {
  const { data } = await http.patch<TaskTemplate>(`/task-templates/${templateId}`, payload)
  return data
}

export async function instantiateTaskTemplate(
  templateId: string,
  payload: InstantiateTaskTemplatePayload,
): Promise<TaskTemplateInstantiation> {
  const { data } = await http.post<TaskTemplateInstantiation>(
    `/task-templates/${templateId}/instantiate`,
    payload,
  )
  return data
}

export async function listTaskTemplateInstances(
  templateId: string,
  limit = 10,
): Promise<TaskTemplateInstance[]> {
  const { data } = await http.get<TaskTemplateInstance[]>(`/task-templates/${templateId}/instances`, {
    params: { limit },
  })
  return data
}

export async function listTaskSchedules(): Promise<TaskSchedule[]> {
  const { data } = await http.get<TaskSchedule[]>('/task-templates/schedules/list')
  return data
}

export async function createTaskSchedule(payload: CreateTaskSchedulePayload): Promise<TaskSchedule> {
  const { data } = await http.post<TaskSchedule>('/task-templates/schedules', payload)
  return data
}

export async function updateTaskSchedule(
  scheduleId: string,
  payload: UpdateTaskSchedulePayload,
): Promise<TaskSchedule> {
  const { data } = await http.patch<TaskSchedule>(`/task-templates/schedules/${scheduleId}`, payload)
  return data
}
