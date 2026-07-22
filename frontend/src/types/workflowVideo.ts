/**
 * Video workflow v1 API-aligned types (W1). Mirrors backend/app/schemas/workflow_video.py.
 */

import type { TemplateCapabilities } from '@/types/api'

export type VideoRunKind = 'batch' | 'production'

export interface VideoApprovedTopic {
  topic_id: string
  title: string
  content?: string | null
  reason?: string | null
  source_submitter_id?: string | null
  source_node_instance_id?: string | null
  script_author_id: string
  due_at?: string | null
}

export interface ParticipantUserPreview {
  id: string
  email: string
  display_name?: string | null
}

export interface TopicCaptureSubmitResponse {
  task_id: string
  node_instance_id: string
  topic_count: number
  topics: Array<{
    topic_id?: string
    title: string
    content?: string | null
    reason?: string | null
  }>
}

export interface InstanceSubmissionsResponse {
  instance_id: string
  node_key: string
  submissions: Array<{
    node_instance_id: string
    node_key: string
    instance_key: string
    assignee_user_id: string | null
    assignee_email?: string | null
    assignee_display_name?: string | null
    submitted_at?: string | null
    topics: TopicCaptureSubmitResponse['topics']
  }>
}

export interface FinalizeTopicsResponse {
  instance_id: string
  approved_count: number
  fork_status: string
  fork_deferred: boolean
  message?: string | null
}

export interface CloseCaptureResponse {
  instance_id: string
  capture_closed: boolean
  capture_closed_at: string
  skipped_capture_count: number
  message: string
}

export interface DispatchTopicRequest {
  topic_id: string
  title: string
  script_writer_user_id: string
  source_node_instance_id?: string | null
}

export interface DispatchTopicResponse {
  instance_id: string
  child_instance_id: string
  fork_status: string
  message?: string | null
}

export interface RejectedCaptureItem {
  reason: string
  topic_id?: string
  instance_key?: string
}

export interface RejectCapturesRequest {
  rejections: RejectedCaptureItem[]
  source_node_key?: string
}

export interface RejectCapturesResponse {
  instance_id: string
  reopened_count: number
  reopened_instance_keys: string[]
}

export interface RejectProductionStepRequest {
  reason: string
  target_node_key?: string | null
}

export interface RejectProductionStepResponse {
  instance_id: string
  target_node_key: string
  target_node_instance_id: string
  iteration: number
}

export interface ForkProductionRunsResponse {
  batch_instance_id: string
  forked_count: number
  skipped_count: number
  child_instance_ids: string[]
  fork_status: string
}

export interface CreateGraphTemplateRunRequest {
  inputs?: Record<string, unknown>
  participants_snapshot: Record<
    string,
    { mode: 'all' | 'subset'; user_ids: string[]; include_initiator?: boolean }
  >
  department_id?: string | null
  run_label?: string | null
}

export interface CreateGraphTemplateRunResponse {
  instance_id: string
  root_task_id: string
  run_kind: string
  activated_task_count: number
  node_instance_count: number
  current_node_key?: string | null
}

export interface PreviewParticipantsResponse {
  policy_ref: string
  mode: 'all' | 'subset'
  user_ids: string[]
  users: ParticipantUserPreview[]
  snapshot: {
    mode: 'all' | 'subset'
    user_ids: string[]
    include_initiator?: boolean
  }
}

export interface LaunchSchemaField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'datetime' | 'user' | string
  required?: boolean
}

export interface LaunchSchema {
  fields: LaunchSchemaField[]
}

export interface CaptureSchemaColumn {
  key: string
  label: string
  type: 'text' | 'textarea' | 'user' | 'datetime' | string
  required?: boolean
  pool_key?: string | null
}

export interface CaptureSchema {
  mode: 'row_table'
  min_rows?: number
  max_rows?: number
  columns: CaptureSchemaColumn[]
}

export interface GraphTemplateSummary {
  id: string
  code: string
  name: string
  description?: string | null
  status: string
  version: number
  /** @deprecated Legacy video v1 product type from config.run_kind. Prefer capabilities. */
  run_kind?: string | null
  tags?: string[]
  capabilities?: TemplateCapabilities
  config?: Record<string, unknown>
  scope_mode?: 'global' | 'departments'
  scope_department_ids?: string[]
  run_count_total?: number | null
  run_count_30d?: number | null
  active_run_count?: number | null
}

export interface GraphTemplateNodeDetail {
  id: string
  node_key: string
  title: string
  sort_order: number
  node_type?: string
  assignment_mode?: string
  join_mode?: string
  routing_mode?: 'exclusive' | 'inclusive' | 'parallel' | 'first_match'
  assignee_rule?: Record<string, unknown>
  config?: Record<string, unknown>
}

export interface GraphTemplateEdgeDetail {
  id?: string | null
  from_node_key: string
  to_node_key: string
  is_reject_path: boolean
  condition?: Record<string, unknown>
  priority?: number
}

export interface GraphTemplateDesignerDetail extends GraphTemplateSummary {
  base_code: string
  source_template_id?: string | null
  has_instances: boolean
  structure_locked: boolean
  nodes: GraphTemplateNodeDetail[]
  edges?: GraphTemplateEdgeDetail[]
}

export interface GraphTemplateValidateResult {
  valid: boolean
  errors: string[]
}

export interface GraphTemplateExportBundle {
  format_version: number
  template: {
    name: string
    description?: string | null
    config?: Record<string, unknown>
    context_schema?: Record<string, unknown>
    scope_mode?: 'global' | 'departments'
    scope_department_ids?: string[]
    nodes: GraphTemplateNodeDetail[]
    edges?: GraphTemplateEdgeDetail[]
  }
}

export interface GraphTemplateDryRunPolicyPreview {
  policy_ref: string
  mode: string
  user_count: number
  user_ids: string[]
}

export interface GraphTemplateDryRunResult {
  valid: boolean
  errors: string[]
  schema_snapshot: Record<string, unknown>
  normalized_inputs: Record<string, unknown>
  entry_node_keys: string[]
  participant_previews: GraphTemplateDryRunPolicyPreview[]
}

export interface WorkflowGraphInstanceSummary {
  id: string
  template_id: string | null
  status: string
  current_node_key?: string | null
  run_label?: string | null
  parent_instance_id?: string | null
  context: Record<string, unknown>
  progress_percent?: number
  total_node_count?: number
  completed_node_count?: number
  active_task_id?: string | null
}

export interface WorkflowRunEventItem {
  id: string
  instance_id: string
  event_type: string
  event_version: number
  aggregate_version: number | null
  command_id: string | null
  causation_id: string | null
  correlation_id: string | null
  actor_user_id: string | null
  payload: Record<string, unknown>
  occurred_at: string
  created_at: string
}

export interface WorkflowRunEventListResponse {
  instance_id: string
  items: WorkflowRunEventItem[]
  total: number
  limit: number
  offset: number
}

export interface DepartmentRunSummary {
  instance_id: string
  run_label: string | null
  status: string
  created_at: string
  event_count: number
  department_id: string | null
}

export interface VideoRunContext {
  run_kind?: VideoRunKind
  run_label?: string | null
  inputs?: Record<string, unknown>
  participants_snapshot?: Record<
    string,
    { mode: 'all' | 'subset'; user_ids: string[] }
  >
  root_task_id?: string | null
  template_version?: number
  schema_snapshot?: Record<string, unknown>
  approved_topics?: VideoApprovedTopic[]
  fork_status?: 'pending' | 'completed' | 'partial'
  parent_instance_id?: string | null
  topic_id?: string | null
  topic_title?: string | null
  script_author_id?: string | null
  forked_child_instance_ids?: string[]
}

export interface GraphTemplateSchedule {
  id: string
  template_id: string
  template_code?: string | null
  template_name?: string | null
  name: string
  scope_department_id: string
  scope_department_name?: string | null
  scope_mode: 'self' | 'subtree'
  cron_expr: string
  timezone: string
  default_inputs: Record<string, unknown>
  run_label_template?: string | null
  participant_mode: 'all' | 'subset'
  participant_user_ids: string[]
  exclude_department_ids: string[]
  exclude_user_ids: string[]
  is_active: boolean
  created_by: string
  next_run_at: string | null
  last_run_at: string | null
  last_run_status: string | null
  last_run_message: string | null
  last_run_instance_count: number | null
  created_at: string
  updated_at: string
}

export interface CreateGraphTemplateScheduleRequest {
  template_id: string
  name: string
  scope_department_id: string
  scope_mode?: 'self' | 'subtree'
  cron_expr: string
  timezone?: string
  default_inputs?: Record<string, unknown>
  run_label_template?: string | null
  participant_mode?: 'all' | 'subset'
  participant_user_ids?: string[]
  exclude_department_ids?: string[]
  exclude_user_ids?: string[]
  is_active?: boolean
}

export interface GraphTemplateScheduleRunNowResponse {
  created_count: number
  skipped_count: number
  failed_count: number
  details: Array<Record<string, unknown>>
}
