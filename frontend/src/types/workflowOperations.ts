export type WorkflowOperationAction = {
  id: string
  status: string
  manual_replay_count?: number | null
}

export type WorkflowOperationsIssue = {
  category: string
  severity: string
  instance_id: string | null
  node_instance_id: string | null
  title: string
  message: string
  age_seconds: number | null
}

export type WorkflowOutboxOperation = {
  id: string
  instance_id: string
  node_instance_id: string | null
  event_type: string
  status: string
  attempt_count: number
  available_at: string | null
  last_error: string | null
  manual_replay_count: number
  last_replayed_at: string | null
  last_replayed_by_user_id: string | null
  last_replay_reason: string | null
  updated_at: string
}

export type WorkflowIncidentOperation = {
  id: string
  category: string
  status: string
  severity: string
  occurrence_count: number
  first_seen_at: string
  last_seen_at: string
  resolved_at: string | null
  resolved_by_user_id: string | null
  resolution_note: string | null
  instance_id: string | null
  node_instance_id: string | null
  task_id: string | null
  command_receipt_id: string | null
  outbox_event_id: string | null
  engine_version: string | null
  detail_keys: string[]
}

export type WorkflowProjectionStreamHealth = {
  stream_name: string
  status: string
  processed_count: number
  source_count: number
  backlog_count: number
  lag_seconds: number
  last_success_at: string | null
  last_error: string | null
  sampled_at: string
}

export type WorkflowShadowHealth = {
  scan_id: string
  sample_mode: string
  observed_at: string
  outcomes: Record<string, number>
  severities: Record<string, number>
}

export type WorkflowOperationsDashboard = {
  generated_at: string
  stalled_minutes: number
  metrics: {
    runs: Record<string, number>
    stalled_run_count: number
    suspended_node_count: number
    join_wait_count: number
    oldest_join_wait_seconds: number
    outbox: Record<string, number>
    outbox_backlog_count: number
    oldest_outbox_backlog_seconds: number
    projection_failed_stream_count: number
  }
  projection_streams: WorkflowProjectionStreamHealth[]
  shadow: WorkflowShadowHealth | null
  issues: WorkflowOperationsIssue[]
  failed_outbox: WorkflowOutboxOperation[]
  incidents: WorkflowIncidentOperation[]
}

export type WorkflowTrace = {
  id: string
  event_type: string
  occurred_at: string
  request_id: string | null
  command_id: string | null
  correlation_id: string | null
  instance_id: string
  node_instance_id: string | null
  task_id: string | null
  actor_user_id: string | null
  payload_keys: string[]
}

export type WorkflowTraceList = {
  items: WorkflowTrace[]
}

export type WorkflowTraceFilters = Partial<{
  request_id: string
  command_id: string
  correlation_id: string
  instance_id: string
  node_instance_id: string
  task_id: string
}>
