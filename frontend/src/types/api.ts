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
export type AttachmentTargetType =
  | 'task_comment'
  | 'task'
  | 'profile'
  | 'document'
  | 'notification_message'
  | 'report'
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
export type NotificationChannel = 'email' | 'web_push' | 'websocket'
export type NotificationMessageStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type NotificationDeliveryStatus = 'pending' | 'sent' | 'failed' | 'retrying'
export type NotificationReceiptType = 'delivered' | 'read' | 'acknowledged'
export type MessageStateFilter = 'all' | 'unread' | 'read' | 'unacknowledged' | 'acknowledged'
export type PushSubscriptionStatus = 'active' | 'expired' | 'revoked'
export type DocumentCategory = 'policy' | 'sop' | 'announcement' | 'faq' | 'other'
export type DocumentStatus = 'draft' | 'published' | 'archived'
export type DepartmentCapability =
  | 'publish_announcement'
  | 'publish_org_task'
  | 'manage_templates'
export type WorkflowDefinitionStatus = 'draft' | 'active' | 'archived'
export type WorkflowStepType = 'task' | 'approval' | 'notify'
export type ApprovalMode = 'single' | 'parallel_all' | 'parallel_any'
export type WorkflowInstanceStatus =
  | 'pending'
  | 'in_progress'
  | 'approved'
  | 'rejected'
  | 'returned'
  | 'cancelled'
  | 'completed'
export type WorkflowStepRunStatus = 'pending' | 'approved' | 'rejected' | 'returned' | 'delegated' | 'skipped'

export interface User {
  id: string
  email: string
  role: UserRole
  status: UserStatus
  last_login_at: string | null
  invited_by?: string | null
  invitation_sent_at?: string | null
  invitation_expires_at?: string | null
  invitation_revoked_at?: string | null
  invitation_accepted_at?: string | null
  created_at: string
  updated_at: string
}

export interface UserInvitation {
  user: User
  invite_url: string
  expires_at: string
}

export interface UserInvitationPreview {
  user_id: string
  email: string
  role: UserRole
  expires_at: string
}

export interface AuthSession {
  access_token: string
  token_type: string
  user: User
}

export interface Department {
  id: string
  name: string
  code: string
  parent_id: string | null
  manager_id: string | null
  capabilities?: DepartmentCapability[]
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

export interface PeopleManagementSummary {
  total_people: number
  profiled_people: number
  unprofiled_people: number
  inactive_people: number
}

export interface PeopleManagementPerson {
  user_id: string
  email: string
  role: UserRole
  status: UserStatus
  last_login_at: string | null
  has_profile: boolean
  profile_completion_state: string
  employee_no: string | null
  real_name: string | null
  department_id: string | null
  department_name: string | null
  job_title: string | null
  hire_date: string | null
  updated_at: string
}

export interface PeopleManagementActions {
  can_edit_user: boolean
  can_delete_user: boolean
  can_create_profile: boolean
  can_edit_profile: boolean
  can_manage_relations: boolean
  can_manage_lifecycle: boolean
  can_manage_delegations: boolean
}

export interface PeopleManagementSnapshot {
  summary: PeopleManagementSummary
  people: PeopleManagementPerson[]
}

export interface PeopleManagementDetail {
  summary: PeopleManagementPerson
  account: User
  profile: Profile | null
  actions: PeopleManagementActions
  primary_manager_user_id: string | null
  primary_manager_label: string | null
  latest_employment_event: EmploymentEvent | null
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

export interface TaskWatcher {
  id: string
  task_id: string
  user_id: string
  relation: string
  created_by: string
  created_at: string
}

export interface TaskBoardColumn {
  status: TaskStatus
  tasks: Task[]
}

export interface TaskGanttEntry {
  task: Task
  dependency_ids: string[]
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
  author_label?: string | null
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
  operator_label?: string | null
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
  assignee_label: string
  department_id: string | null
  department_name: string | null
  total_tasks: number
  open_tasks: number
  completed_tasks: number
  overdue_tasks: number
}

export interface TaskSchedule {
  id: string
  template_id: string
  owner_user_id: string
  cron_expr: string
  timezone: string
  next_run_at: string | null
  is_active: boolean
  payload: Record<string, unknown>
  last_run_at: string | null
  last_run_status: 'success' | 'failed' | null
  last_run_message: string | null
  last_run_task_count: number | null
  created_at: string
  updated_at: string
}

export interface OverviewScopeOption {
  id: string
  label: string
}

export interface OverviewBoardCard {
  id: string
  scope_department_id: string | null
  scope_label: string
  title: string
  content_md: string
  expires_at: string
  author_user_id: string
  author_name: string
  created_at: string
}

export interface OverviewAnnouncement {
  id: string
  publisher_department_id: string
  publisher_department_name: string
  title: string
  content_md: string
  published_at: string
  author_user_id: string
  author_name: string
}

export interface OverviewTaskInboxEntry {
  task_id: string
  title: string
  priority: TaskPriority
  status: TaskStatus
  due_date: string | null
  department_name: string | null
  current_stage_label: string
  current_handler_label: string | null
}

export interface OverviewTaskTrackingEntry {
  task_id: string
  title: string
  priority: TaskPriority
  status: TaskStatus
  due_date: string | null
  department_name: string | null
  relation_types: string[]
  current_stage_label: string
  current_handler_label: string | null
}

export interface OverviewPermissions {
  board_scope_options: OverviewScopeOption[]
  announcement_scope_options: OverviewScopeOption[]
  can_publish_board: boolean
  can_publish_announcement: boolean
}

export interface OverviewSnapshot {
  board_cards: OverviewBoardCard[]
  announcements: OverviewAnnouncement[]
  task_inbox: OverviewTaskInboxEntry[]
  task_tracking: OverviewTaskTrackingEntry[]
  permissions: OverviewPermissions
}

export interface TaskCenterTemplateSummary {
  id: string
  name: string
  category: string
  is_active: boolean
  step_count: number
}

export interface TaskCenterDepartmentOption {
  id: string
  label: string
}

export interface TaskCenterUserOption {
  user_id: string
  email: string
  real_name: string | null
  department_id: string | null
  department_name: string | null
  label: string
}

export interface TaskCenterInboxItem {
  task_id: string
  title: string
  priority: TaskPriority
  status: TaskStatus
  due_date: string | null
  department_name: string | null
  current_stage_label: string
  current_handler_label: string | null
  run_label?: string | null
  user_facing_state?: string | null
}

export interface TaskCenterTrackingItem {
  task_id: string
  title: string
  priority: TaskPriority
  status: TaskStatus
  due_date: string | null
  department_name: string | null
  relation_types: string[]
  current_stage_label: string
  current_handler_label: string | null
  latest_deliverable_submitted_at?: string | null
  rework_count?: number
  review_quality_score?: number | null
  is_pending_review?: boolean
  run_label?: string | null
  user_facing_state?: string | null
}

export interface TaskCenterHistoryItem {
  task_id: string
  title: string
  priority: TaskPriority
  due_date: string | null
  completed_at: string | null
  department_name: string | null
  relation_types: string[]
  source_type: TaskSourceType
  run_label?: string | null
  user_facing_state?: string | null
}

export interface TaskCenterTaskReference {
  id: string
  title: string
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
}

export interface TaskMemo {
  id: string
  owner_user_id: string
  related_task_id: string | null
  title: string | null
  content: string
  is_pinned: boolean
  created_at: string
  updated_at: string
  related_task: TaskCenterTaskReference | null
}

export interface TaskCenterPermissions {
  can_manage_templates: boolean
  can_publish_task: boolean
}

export interface TaskCenterPagination {
  next_cursor: string | null
  has_more: boolean
}

export interface TaskCenterSnapshot {
  permissions: TaskCenterPermissions
  template_summaries: TaskCenterTemplateSummary[]
  publish_department_options: TaskCenterDepartmentOption[]
  publish_user_options: TaskCenterUserOption[]
  task_inbox: TaskCenterInboxItem[]
  task_tracking: TaskCenterTrackingItem[]
  task_history: TaskCenterHistoryItem[]
  task_memos: TaskMemo[]
  inbox_pagination?: TaskCenterPagination
  tracking_pagination?: TaskCenterPagination
  history_pagination?: TaskCenterPagination
}

export interface TaskTemplateStep {
  id: string
  template_id: string
  step_key: string
  title: string
  description: string | null
  step_type: string
  assignment_mode: string
  join_mode: string
  default_assignee_rule: Record<string, unknown>
  default_due_offset_hours: number | null
  sort_order: number
  config: Record<string, unknown>
  approval_type: string
  reject_target_step_key: string | null
  downstream_trigger: Record<string, unknown> | null
  created_at: string
  updated_at: string
  depends_on_step_keys: string[]
}

export interface TaskTemplate {
  id: string
  code: string
  base_code: string
  version: number
  name: string
  category: string
  description: string | null
  trigger_type: string
  config: Record<string, unknown>
  is_active: boolean
  created_by: string
  source_template_id: string | null
  latest_version: number
  has_instances: boolean
  is_structure_locked: boolean
  created_at: string
  updated_at: string
  steps: TaskTemplateStep[]
  schedules: TaskSchedule[]
}

export type TaskTemplateInstanceStatus = 'in_progress' | 'completed' | 'cancelled'
export type TaskTemplateStepSnapshotStatus = 'blocked' | 'ready' | 'active' | 'completed'
export type TaskTemplateStepRunDecision = 'approved' | 'rejected' | 'returned'
export type TaskTemplateStepRunStatus = 'active' | 'completed' | 'skipped' | 'cancelled'

export interface TaskTemplateStepRun {
  id: string
  instance_id: string
  template_step_id: string
  assignee_user_id: string
  assignee_email: string | null
  assignee_label?: string | null
  iteration: number
  status: TaskTemplateStepRunStatus
  decision: TaskTemplateStepRunDecision | null
  result_payload: Record<string, unknown> | null
  completed_at: string | null
  created_at: string
  updated_at: string
  task: Task | null
}

export interface TaskTemplateStepSnapshot {
  step: TaskTemplateStep
  status: TaskTemplateStepSnapshotStatus
  blocked_dependency_keys: string[]
  total_run_count: number
  active_run_count: number
  completed_run_count: number
  history_iteration_count: number
  latest_iteration: number
  step_runs: TaskTemplateStepRun[]
}

export interface TaskTemplateInstance {
  id: string
  template_id: string
  initiator_user_id: string
  initiator_email: string | null
  initiator_label?: string | null
  department_id: string | null
  department_name: string | null
  status: TaskTemplateInstanceStatus
  payload: Record<string, unknown>
  completed_at: string | null
  total_step_count: number
  completed_step_count: number
  active_step_count: number
  blocked_step_count: number
  ready_step_count: number
  progress_percent: number
  created_at: string
  updated_at: string
  step_snapshots: TaskTemplateStepSnapshot[]
}

export interface TaskTemplateInstantiation {
  template: TaskTemplate
  instance: TaskTemplateInstance
  tasks: Task[]
}

export interface WorkflowStep {
  id: string
  definition_id: string
  step_key: string
  name: string
  step_type: WorkflowStepType
  approval_mode: ApprovalMode | null
  assignee_rule: Record<string, unknown>
  reject_target_step_key: string | null
  sort_order: number
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface WorkflowDefinition {
  id: string
  code: string
  name: string
  scope_type: string
  status: WorkflowDefinitionStatus
  version: number
  config: Record<string, unknown>
  created_by: string
  created_at: string
  updated_at: string
  steps: WorkflowStep[]
}

export interface WorkflowStepRun {
  id: string
  instance_id: string
  step_id: string
  assignee_user_id: string
  delegated_from_user_id: string | null
  status: WorkflowStepRunStatus
  acted_at: string | null
  comment: string | null
  payload: Record<string, unknown>
  created_at: string
  updated_at: string
  step: WorkflowStep | null
}

export interface WorkflowInstance {
  id: string
  definition_id: string
  source_type: string
  source_id: string | null
  initiator_user_id: string
  status: WorkflowInstanceStatus
  current_step_key: string | null
  payload: Record<string, unknown>
  started_at: string
  completed_at: string | null
  created_at: string
  updated_at: string
  step_runs: WorkflowStepRun[]
  definition: WorkflowDefinition | null
}

export type ReportDirection = 'upward' | 'downward'
export type ReportStatus = 'in_progress' | 'completed' | 'returned' | 'archived'
export type ReportRouteStatus = 'queued' | 'pending' | 'forwarded' | 'completed' | 'returned'

export interface ReportActionOption {
  action: string
  label: string
  button_type: string
}

export interface ReportTargetOption {
  user_id: string
  label: string
  path_labels: string[]
  hops: number
}

export interface WorkflowDefinitionOption {
  id: string
  name: string
}

export interface ReportRoute {
  id: string
  sequence_no: number
  sender_user_id: string
  sender_label: string
  recipient_user_id: string
  recipient_label: string
  assigned_user_id: string | null
  assigned_label: string | null
  status: ReportRouteStatus
  activated_at: string | null
  acted_at: string | null
  note: string | null
}

export interface ReportRecord {
  id: string
  direction: ReportDirection
  status: ReportStatus
  title: string
  content_md: string
  initiator_user_id: string
  initiator_label: string
  target_user_id: string
  target_label: string
  current_recipient_user_id: string | null
  current_recipient_label: string | null
  current_route_sequence: number | null
  workflow_definition_id: string | null
  workflow_definition_name: string | null
  workflow_instance_id: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  returned_at: string | null
  archived_at: string | null
  available_actions: ReportActionOption[]
  routes: ReportRoute[]
  attachments: Attachment[]
}

export interface ReportCenterPermissions {
  can_create_upward: boolean
  can_create_downward: boolean
}

export interface ReportCenterSnapshot {
  permissions: ReportCenterPermissions
  upward_target_options: ReportTargetOption[]
  downward_target_options: ReportTargetOption[]
  workflow_definition_options: WorkflowDefinitionOption[]
  pending_reports: ReportRecord[]
  initiated_reports: ReportRecord[]
  history_reports: ReportRecord[]
}

export interface NotificationDelivery {
  id: string
  message_id: string
  channel: NotificationChannel
  adapter_name: string
  status: NotificationDeliveryStatus
  attempt_count: number
  external_message_id: string | null
  error_message: string | null
  attempted_at: string | null
  delivered_at: string | null
  created_at: string
}

export interface NotificationReceipt {
  id: string
  message_id: string
  user_id: string
  receipt_type: NotificationReceiptType
  note: string | null
  created_at: string
}

export interface MessageSourceTarget {
  route_name: string | null
  route_query: Record<string, string>
  can_navigate: boolean
}

export interface MessageSource {
  module_key: string
  module_label: string
  object_type: string
  object_id: string | null
  object_label: string | null
  target: MessageSourceTarget
}

export interface MessageReceiptState {
  is_read: boolean
  is_acknowledged: boolean
  read_at: string | null
  acknowledged_at: string | null
}

export interface Message {
  id: string
  source_type: string
  source_id: string | null
  recipient_user_id: string | null
  recipient_email: string | null
  message_type: string
  title: string
  body_text: string
  body_html: string | null
  payload: Record<string, unknown>
  status: NotificationMessageStatus
  scheduled_at: string | null
  enqueued_at: string | null
  completed_at: string | null
  created_at: string
  delivery_state: NotificationDeliveryStatus | null
  source: MessageSource
  receipt_state: MessageReceiptState
  attachments: Attachment[]
  deliveries: NotificationDelivery[]
  receipts: NotificationReceipt[]
}

export interface MessageSourceCount {
  source_type: string
  label: string
  count: number
}

export interface MessageCenterSnapshot {
  items: Message[]
  total_count: number
  filtered_count: number
  unread_count: number
  unacknowledged_count: number
  source_counts: MessageSourceCount[]
  applied_source_type: string | null
  applied_state: MessageStateFilter
  applied_channel: NotificationChannel | null
  applied_delivery_status: NotificationDeliveryStatus | null
  applied_created_from: string | null
  applied_created_to: string | null
}

export interface DocumentSummary {
  id: string
  title: string
  slug: string
  category: DocumentCategory
  status: DocumentStatus
  author_id: string
  version: number
  published_at: string | null
  created_at: string
  updated_at: string
  author_email: string | null
}

export interface Document extends DocumentSummary {
  content_md: string
  attachments: Attachment[]
}

export interface DocumentSearchHit {
  document_id: string
  title: string
  slug: string
  category: DocumentCategory
  status: DocumentStatus
  score: number
  chunk_index: number
  excerpt: string
}

export interface DocumentSearchResponse {
  query: string
  items: DocumentSearchHit[]
}

export interface KnowledgeQueryResult {
  query: string
  context: string
  hits: DocumentSearchHit[]
}

export interface AIRouterResult {
  mode: string
  prompt: string
  reply_text: string
  command_name: string | null
  tool_results: Record<string, unknown>[]
  knowledge_hits: DocumentSearchHit[]
}

export interface PushSubscription {
  id: string
  user_id: string
  endpoint: string
  status: PushSubscriptionStatus
  user_agent: string | null
  last_seen_at: string | null
  created_at: string
  updated_at: string
}

// ─── Workflow Graph Engine ─────────────────────────────────────────────────

export type WorkflowGraphInstanceStatus =
  | 'pending'
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'terminated'

export type WorkflowNodeEngineState =
  | 'pending'
  | 'activated'
  | 'acknowledged'
  | 'completed'
  | 'terminated'

export type WorkflowGraphNodeType = 'task' | 'approval' | 'notice'

export type WorkflowNodeBusinessState =
  | 'draft'
  | 'assigned'
  | 'accepted'
  | 'rejected'
  | 'delegated'
  | 'doing'
  | 'pending_review'
  | 'done'
  | 'returned_for_rework'
  | 'cancelled'

export interface WorkflowNodeInstanceSummary {
  id: string
  instance_id: string
  instance_key?: string
  template_node_id: string | null
  node_key: string
  title: string
  node_type: WorkflowGraphNodeType
  engine_state: WorkflowNodeEngineState
  business_state: WorkflowNodeBusinessState
  assignee_user_id: string | null
  iteration: number
  activated_at: string | null
  completed_at: string | null
  terminated_at: string | null
  created_at: string
  task_id?: string | null
}

export interface WorkflowGraphInstanceDetail {
  id: string
  template_id: string | null
  initiator_user_id: string
  department_id: string | null
  source_type: string | null
  status: WorkflowGraphInstanceStatus
  current_node_key: string | null
  run_label?: string | null
  parent_instance_id?: string | null
  context: Record<string, unknown>
  context_version: number
  max_iterations: number
  completed_at: string | null
  created_at: string
  node_instances: WorkflowNodeInstanceSummary[]
  total_node_count: number
  completed_node_count: number
  active_node_count: number
  pending_node_count: number
  progress_percent: number
}
