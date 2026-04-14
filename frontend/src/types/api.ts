export type UserRole = 'admin' | 'hr' | 'employee'
export type UserStatus = 'active' | 'inactive' | 'suspended' | 'offboarded'
export type TaskStatus = 'todo' | 'doing' | 'review' | 'done'
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent'
export type TaskSourceType = 'manual' | 'template' | 'event' | 'ai'
export type TaskActionType =
  | 'created'
  | 'assigned'
  | 'status_changed'
  | 'commented'
  | 'attachment_added'
  | 'due_date_changed'
  | 'closed'
export type CommentFormat = 'plain_text' | 'markdown'
export type AttachmentVisibility = 'private' | 'internal' | 'public'
export type AttachmentStatus = 'uploaded' | 'deleted' | 'quarantined'
export type AttachmentTargetType = 'task_comment' | 'task' | 'profile' | 'document'

export interface User {
  id: string
  email: string
  role: UserRole
  status: UserStatus
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface AuthSession {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface Department {
  id: string
  name: string
  code: string
  parent_id: string | null
  manager_id: string | null
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DepartmentTreeNode extends Omit<Department, 'created_at' | 'updated_at'> {
  children: DepartmentTreeNode[]
}

export interface Profile {
  user_id: string
  employee_no: string
  real_name: string
  department_id: string
  job_title: string | null
  phone: string | null
  hire_date: string | null
  custom_fields: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Task {
  id: string
  title: string
  description: string | null
  creator_id: string
  assignee_id: string
  department_id: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  started_at: string | null
  completed_at: string | null
  parent_task_id: string | null
  source_type: TaskSourceType
  extra_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Attachment {
  id: string
  original_filename: string
  mime_type: string
  size_bytes: number
  checksum_sha256: string
  uploader_id: string
  visibility: AttachmentVisibility
  status: AttachmentStatus
  deleted_at: string | null
  created_at: string
  download_url: string | null
}

export interface TaskComment {
  id: string
  task_id: string
  user_id: string
  content: string
  content_format: CommentFormat
  is_internal: boolean
  created_at: string
  updated_at: string
  attachments: Attachment[]
}

export interface TaskLog {
  id: string
  task_id: string
  operator_id: string
  action_type: TaskActionType
  from_status: TaskStatus | null
  to_status: TaskStatus | null
  detail: Record<string, unknown>
  created_at: string
}

export interface TaskActivityEntry {
  entry_type: 'comment' | 'log'
  created_at: string
  comment: TaskComment | null
  log: TaskLog | null
}

export interface TaskStatsSummary {
  total_tasks: number
  completed_tasks: number
  completion_rate: number
  overdue_tasks: number
  overdue_rate: number
  tasks_by_status: Record<string, number>
}

export interface TaskWorkloadRow {
  assignee_id: string
  assignee_email: string
  department_id: string | null
  department_name: string | null
  total_tasks: number
  open_tasks: number
  completed_tasks: number
  overdue_tasks: number
}
