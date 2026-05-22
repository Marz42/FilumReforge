/**
 * Video workflow v1 API-aligned types (W1). Mirrors backend/app/schemas/workflow_video.py.
 */

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

export interface PreviewParticipantsResponse {
  policy_ref: string
  mode: 'all' | 'subset'
  user_ids: string[]
  users: ParticipantUserPreview[]
  snapshot: {
    mode: 'all' | 'subset'
    user_ids: string[]
  }
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
