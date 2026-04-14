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
export type PositionAssignmentType = 'primary' | 'part_time' | 'acting'
export type ReportingLineType = 'solid' | 'dotted'
export type EmploymentEventType =
  | 'onboard'
  | 'transfer'
  | 'promotion'
  | 'reward'
  | 'discipline'
  | 'offboard'
  | 'rehire'
export type DelegationScopeType = 'approval' | 'task' | 'data_access' | 'all'
export type DelegationStatus = 'pending' | 'active' | 'expired' | 'revoked'

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

export interface ProfileFieldAccess {
  field_key: string
  label: string
  field_type: string
  storage_target: string
  is_sensitive: boolean
  value: unknown
  can_view: boolean
  can_edit: boolean
}

export interface Position {
  id: string
  code: string
  name: string
  level: string | null
  extra_metadata: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProfilePosition {
  id: string
  user_id: string
  position_id: string
  department_id: string
  assignment_type: PositionAssignmentType
  is_primary: boolean
  starts_at: string
  ends_at: string | null
  created_at: string
  updated_at: string
}

export interface ReportingLine {
  id: string
  user_id: string
  manager_user_id: string
  department_id: string | null
  line_type: ReportingLineType
  is_primary: boolean
  starts_at: string
  ends_at: string | null
  created_at: string
  updated_at: string
}

export interface EmploymentEvent {
  id: string
  user_id: string
  event_type: EmploymentEventType
  effective_date: string
  title: string
  summary: string | null
  payload: Record<string, unknown>
  created_by: string
  created_at: string
}

export interface Delegation {
  id: string
  delegator_user_id: string
  delegate_user_id: string
  scope_type: DelegationScopeType
  scope_department_id: string | null
  scope_filters: Record<string, unknown>
  status: DelegationStatus
  starts_at: string
  ends_at: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface ProfileFieldDefinition {
  id: string
  field_key: string
  label: string
  field_type: string
  storage_target: string
  is_sensitive: boolean
  config: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProfileFieldPermission {
  id: string
  field_definition_id: string
  subject_type: string
  subject_value: string | null
  can_view: boolean
  can_edit: boolean
  scope_filters: Record<string, unknown>
  priority: number
  created_at: string
  updated_at: string
}

export interface Profile {
  user_id: string
  user_email: string | null
  user_status: UserStatus | null
  employee_no: string | null
  real_name: string | null
  department_id: string | null
  job_title: string | null
  phone: string | null
  hire_date: string | null
  custom_fields: Record<string, unknown>
  visible_fields: ProfileFieldAccess[]
  positions: ProfilePosition[]
  reporting_lines: ReportingLine[]
  employment_events: EmploymentEvent[]
  delegations: Delegation[]
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
