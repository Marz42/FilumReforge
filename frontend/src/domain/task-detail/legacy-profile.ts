import type { Task } from '@/types/api'

export type LegacyWorkflowSurface =
  | 'run_overview'
  | 'structured_form'
  | 'collection'
  | 'deliverable'
  | 'review'
  | 'manual'

export interface LegacyTaskCapabilityHint {
  legacyId: string
  surface: LegacyWorkflowSurface
  submitMode: 'form' | 'file' | 'form+file' | 'review' | null
  statePolicy: 'default' | 'run_active' | 'submission' | 'collection' | 'deliverable' | 'review'
  variant: string | null
  features: Record<string, boolean>
  rootVisibility: 'normal' | 'overview' | 'hidden_for_non_management'
}

function hint(
  legacyId: string,
  surface: LegacyWorkflowSurface,
  submitMode: LegacyTaskCapabilityHint['submitMode'],
  statePolicy: LegacyTaskCapabilityHint['statePolicy'],
  options: Partial<Pick<LegacyTaskCapabilityHint, 'variant' | 'features' | 'rootVisibility'>> = {},
): LegacyTaskCapabilityHint {
  return {
    legacyId,
    surface,
    submitMode,
    statePolicy,
    variant: options.variant ?? null,
    features: options.features ?? {},
    rootVisibility: options.rootVisibility ?? 'normal',
  }
}

const LEGACY_UI_PROFILE_HINTS: Record<string, LegacyTaskCapabilityHint> = {
  video_batch_root: hint('video_batch_root', 'run_overview', null, 'run_active', {
    features: { tracking: true, run_dashboard: true, capture_progress: true },
    rootVisibility: 'overview',
  }),
  video_production_root: hint('video_production_root', 'run_overview', null, 'run_active', {
    rootVisibility: 'hidden_for_non_management',
  }),
  video_n1_capture: hint('video_n1_capture', 'structured_form', 'form', 'submission', {
    variant: 'capture',
  }),
  video_capture_assign: hint('video_capture_assign', 'structured_form', 'form', 'submission', {
    variant: 'assignment',
  }),
  video_capture_schedule: hint('video_capture_schedule', 'structured_form', 'form', 'submission', {
    variant: 'schedule',
  }),
  video_n2_aggregate: hint('video_n2_aggregate', 'collection', null, 'collection', {
    features: { capture_progress: true, aggregate: true },
  }),
  video_production_step: hint('video_production_step', 'deliverable', 'file', 'deliverable', {
    variant: 'single',
  }),
  video_production_multi: hint('video_production_multi', 'deliverable', 'file', 'deliverable', {
    variant: 'multi',
  }),
  video_production_platform: hint('video_production_platform', 'deliverable', 'file', 'deliverable', {
    variant: 'platform',
  }),
  graph_manual: hint('graph_manual', 'manual', null, 'default'),
}

function inferNodeHint(
  task: Task,
  metadata: Record<string, unknown>,
  currentUserId?: string | null,
): LegacyTaskCapabilityHint | null {
  const key = typeof metadata.template_node_key === 'string' ? metadata.template_node_key : ''
  const isCapture = key.startsWith('N1_') || key.includes('PROPOSE')
  const isAggregate = key.startsWith('N2_') || key.includes('AGGREGATE')
  if (isAggregate) {
    return LEGACY_UI_PROFILE_HINTS.video_n2_aggregate ?? null
  }
  if (isCapture && task.assignee_id === currentUserId && task.status !== 'done') {
    return LEGACY_UI_PROFILE_HINTS.video_n1_capture ?? null
  }
  if (key) {
    const isReview = key.includes('REVIEW') || key.startsWith('N4_') || key.startsWith('N12_')
    return isReview
      ? hint('video_production_step', 'review', 'review', 'review')
      : (LEGACY_UI_PROFILE_HINTS.video_production_step ?? null)
  }
  return null
}

export function resolveLegacyTaskCapabilityHint(
  task: Task,
  metadata: Record<string, unknown>,
  currentUserId?: string | null,
): LegacyTaskCapabilityHint | null {
  const uiProfile = metadata.ui_profile
  if (typeof uiProfile === 'string' && LEGACY_UI_PROFILE_HINTS[uiProfile]) {
    return LEGACY_UI_PROFILE_HINTS[uiProfile] ?? null
  }
  if (metadata.workflow_graph_root_task === true) {
    if (metadata.run_kind === 'batch') return LEGACY_UI_PROFILE_HINTS.video_batch_root ?? null
    if (metadata.run_kind === 'production') return LEGACY_UI_PROFILE_HINTS.video_production_root ?? null
  }
  if (task.source_type === 'template' && typeof metadata.workflow_graph_instance_id === 'string') {
    return inferNodeHint(task, metadata, currentUserId)
  }
  if (
    task.source_type === 'manual'
    && typeof metadata.workflow_graph_instance_id === 'string'
    && typeof metadata.workflow_node_instance_id === 'string'
  ) {
    return LEGACY_UI_PROFILE_HINTS.graph_manual ?? null
  }
  return null
}

export function resolveCollectionSourceNodeKey(task: Task): string {
  const metadata = (task.extra_metadata as Record<string, unknown> | undefined) ?? {}
  return typeof metadata.collection_source_node_key === 'string'
    ? metadata.collection_source_node_key
    : 'N1_PROPOSE'
}

export function resolveInstanceCapabilities(context: Record<string, unknown> | undefined): Set<string> {
  const snapshot = context?.capability_snapshot
  if (snapshot && typeof snapshot === 'object' && !Array.isArray(snapshot)) {
    const raw = (snapshot as Record<string, unknown>).capabilities
    if (Array.isArray(raw)) {
      return new Set(raw.filter((item): item is string => typeof item === 'string'))
    }
  }
  if (context?.run_kind === 'batch') {
    return new Set([
      'structured_form_submission',
      'collection_finalize',
      'aggregate_confirmation',
      'child_run_dispatch',
    ])
  }
  if (context?.run_kind === 'production') {
    return new Set(['deliverable_submission', 'deliverable_acceptance', 'return_for_rework'])
  }
  return new Set()
}
