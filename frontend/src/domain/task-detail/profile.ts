import type { Task, TaskStatus } from '@/types/api'

import { resolveLegacyTaskCapabilityHint } from './legacy-profile'

export type TaskDetailProfileId =
  | 'workflow_run_overview'
  | 'workflow_structured_form'
  | 'workflow_collection'
  | 'workflow_deliverable'
  | 'workflow_review'
  | 'video_n1_capture'
  | 'video_n2_aggregate'
  | 'video_batch_root'
  | 'video_production_root'
  | 'video_production_step'
  | 'video_production_multi'
  | 'video_production_platform'
  | 'video_capture_assign'
  | 'video_capture_schedule'
  | 'graph_manual'
  | 'legacy_task'

export type TaskSubmitMode = 'form' | 'file' | 'form+file' | 'review'
export type WorkflowTaskSurface =
  | 'run_overview'
  | 'structured_form'
  | 'collection'
  | 'deliverable'
  | 'review'
  | 'manual'
  | 'legacy'
export type WorkflowTaskStatePolicy =
  | 'default'
  | 'run_active'
  | 'submission'
  | 'collection'
  | 'deliverable'
  | 'review'

export interface TaskDetailProfile {
  id: TaskDetailProfileId
  surface: WorkflowTaskSurface
  statePolicy: WorkflowTaskStatePolicy
  variant: string | null
  features: Record<string, boolean>
  rootVisibility: 'normal' | 'overview' | 'hidden_for_non_management'
  submitMode: TaskSubmitMode | null
  hideDeliverable: boolean
  hideHandshakeFields: boolean
  hideWatchers: boolean
  collapseComments: boolean
  compactMetadata: boolean
  showCaptureProgress: boolean
}

export interface ResolveTaskDetailProfileOptions {
  currentUserId?: string | null
}

interface TaskCapabilityMetadata {
  surface: Exclude<WorkflowTaskSurface, 'legacy'>
  statePolicy: WorkflowTaskStatePolicy
  variant: string | null
  features: Record<string, boolean>
  rootVisibility: TaskDetailProfile['rootVisibility']
  submitMode: TaskSubmitMode | null
}

const WORKFLOW_PROFILE_DEFAULTS = {
  hideDeliverable: true,
  hideHandshakeFields: true,
  hideWatchers: true,
  collapseComments: true,
  compactMetadata: true,
}

function readMetadata(task: Task | null | undefined): Record<string, unknown> {
  return (task?.extra_metadata as Record<string, unknown> | undefined) ?? {}
}

function readTaskCapability(metadata: Record<string, unknown>): TaskCapabilityMetadata | null {
  const raw = metadata.task_capability
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const payload = raw as Record<string, unknown>
  const surfaces: TaskCapabilityMetadata['surface'][] = [
    'run_overview', 'structured_form', 'collection', 'deliverable', 'review', 'manual',
  ]
  if (typeof payload.surface !== 'string' || !surfaces.includes(payload.surface as TaskCapabilityMetadata['surface'])) {
    return null
  }
  const submitModes: TaskSubmitMode[] = ['form', 'file', 'form+file', 'review']
  const statePolicies: WorkflowTaskStatePolicy[] = [
    'default', 'run_active', 'submission', 'collection', 'deliverable', 'review',
  ]
  const rootVisibilities: TaskDetailProfile['rootVisibility'][] = [
    'normal', 'overview', 'hidden_for_non_management',
  ]
  const rawFeatures = payload.features
  const features: Record<string, boolean> = {}
  if (rawFeatures && typeof rawFeatures === 'object' && !Array.isArray(rawFeatures)) {
    for (const [key, value] of Object.entries(rawFeatures as Record<string, unknown>)) {
      features[key] = value === true
    }
  }
  return {
    surface: payload.surface as TaskCapabilityMetadata['surface'],
    submitMode: typeof payload.submit_mode === 'string' && submitModes.includes(payload.submit_mode as TaskSubmitMode)
      ? payload.submit_mode as TaskSubmitMode
      : null,
    statePolicy: typeof payload.state_policy === 'string' && statePolicies.includes(payload.state_policy as WorkflowTaskStatePolicy)
      ? payload.state_policy as WorkflowTaskStatePolicy
      : 'default',
    variant: typeof payload.variant === 'string' ? payload.variant : null,
    features,
    rootVisibility: typeof payload.root_visibility === 'string'
      && rootVisibilities.includes(payload.root_visibility as TaskDetailProfile['rootVisibility'])
      ? payload.root_visibility as TaskDetailProfile['rootVisibility']
      : 'normal',
  }
}

function genericProfileId(surface: TaskCapabilityMetadata['surface']): TaskDetailProfileId {
  switch (surface) {
    case 'run_overview': return 'workflow_run_overview'
    case 'structured_form': return 'workflow_structured_form'
    case 'collection': return 'workflow_collection'
    case 'deliverable': return 'workflow_deliverable'
    case 'review': return 'workflow_review'
    case 'manual': return 'graph_manual'
  }
}

function buildProfile(
  capability: TaskCapabilityMetadata,
  id: TaskDetailProfileId = genericProfileId(capability.surface),
): TaskDetailProfile {
  if (capability.surface === 'manual') {
    return {
      id,
      ...capability,
      hideDeliverable: false,
      hideHandshakeFields: false,
      hideWatchers: false,
      collapseComments: false,
      compactMetadata: false,
      showCaptureProgress: false,
    }
  }
  const expandedDeliverable = capability.surface === 'deliverable'
    && capability.variant !== 'single'
  return {
    id,
    ...capability,
    ...WORKFLOW_PROFILE_DEFAULTS,
    hideDeliverable: capability.surface === 'deliverable'
      ? capability.submitMode === 'file'
      : true,
    hideWatchers: expandedDeliverable ? false : WORKFLOW_PROFILE_DEFAULTS.hideWatchers,
    collapseComments: expandedDeliverable ? false : WORKFLOW_PROFILE_DEFAULTS.collapseComments,
    showCaptureProgress: capability.features.capture_progress === true,
  }
}

function legacyId(value: string): TaskDetailProfileId {
  return value as TaskDetailProfileId
}

function legacyProfile(task: Task, metadata: Record<string, unknown>, currentUserId?: string | null) {
  const hint = resolveLegacyTaskCapabilityHint(task, metadata, currentUserId)
  if (!hint) return null
  return buildProfile({
    surface: hint.surface,
    submitMode: hint.submitMode,
    statePolicy: hint.statePolicy,
    variant: hint.variant,
    features: hint.features,
    rootVisibility: hint.rootVisibility,
  }, legacyId(hint.legacyId))
}

function legacyTaskProfile(): TaskDetailProfile {
  return {
    id: 'legacy_task',
    surface: 'legacy',
    statePolicy: 'default',
    variant: null,
    features: {},
    rootVisibility: 'normal',
    submitMode: null,
    hideDeliverable: false,
    hideHandshakeFields: false,
    hideWatchers: false,
    collapseComments: false,
    compactMetadata: false,
    showCaptureProgress: false,
  }
}

export function resolveTaskDetailProfile(
  task: Task | null | undefined,
  options: ResolveTaskDetailProfileOptions = {},
): TaskDetailProfile {
  if (!task) return legacyTaskProfile()
  const metadata = readMetadata(task)
  const explicitCapability = readTaskCapability(metadata)
  if (explicitCapability) return buildProfile(explicitCapability)
  return legacyProfile(task, metadata, options.currentUserId ?? null) ?? legacyTaskProfile()
}

export function usesWorkflowCapabilityLayout(profile: TaskDetailProfile): boolean {
  return profile.surface !== 'legacy' && profile.surface !== 'manual'
}

/** @deprecated Compatibility helper for callers/tests during the profile migration. */
export function isVideoWorkflowProfile(profile: TaskDetailProfile): boolean {
  return usesWorkflowCapabilityLayout(profile)
}

export function shouldShowLegacyStatusActions(
  profile: TaskDetailProfile,
  taskStatus: TaskStatus,
): boolean {
  if (profile.surface === 'manual' || profile.surface === 'legacy') return true
  if (profile.surface === 'deliverable' && taskStatus !== 'review') {
    return profile.submitMode !== 'file'
  }
  return false
}
