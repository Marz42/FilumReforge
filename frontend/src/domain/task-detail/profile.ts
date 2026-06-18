import type { Task, TaskStatus } from '@/types/api'

export type TaskDetailProfileId =
  | 'video_n1_capture'
  | 'video_n2_aggregate'
  | 'video_batch_root'
  | 'video_production_step'
  | 'video_production_multi'
  | 'video_production_platform'
  | 'video_capture_assign'
  | 'video_capture_schedule'
  | 'graph_manual'
  | 'legacy_task'

export type TaskSubmitMode = 'form' | 'file' | 'form+file' | 'review'

export interface TaskDetailProfile {
  id: TaskDetailProfileId
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

function readMetadata(task: Task | null | undefined): Record<string, unknown> {
  return (task?.extra_metadata as Record<string, unknown> | undefined) ?? {}
}

function isGraphTemplateTask(task: Task, metadata: Record<string, unknown>): boolean {
  return task.source_type === 'template'
    && typeof metadata.workflow_graph_instance_id === 'string'
}

function isGraphHandshakeTask(task: Task, metadata: Record<string, unknown>): boolean {
  return task.source_type === 'manual'
    && typeof metadata.workflow_graph_instance_id === 'string'
    && typeof metadata.workflow_node_instance_id === 'string'
}

function nodeKey(metadata: Record<string, unknown>): string {
  return typeof metadata.template_node_key === 'string' ? metadata.template_node_key : ''
}

function runKind(metadata: Record<string, unknown>): string {
  return typeof metadata.run_kind === 'string' ? metadata.run_kind : ''
}

function isCaptureNode(nodeKeyValue: string): boolean {
  return nodeKeyValue.startsWith('N1_') || nodeKeyValue.includes('PROPOSE')
}

function isAggregateNode(nodeKeyValue: string): boolean {
  return nodeKeyValue.startsWith('N2_') || nodeKeyValue.includes('AGGREGATE')
}

function inferSubmitMode(nodeKeyValue: string): TaskSubmitMode {
  if (isCaptureNode(nodeKeyValue)) {
    return 'form'
  }
  if (
    nodeKeyValue.includes('REVIEW')
    || nodeKeyValue.startsWith('N4_')
    || nodeKeyValue.startsWith('N12_')
  ) {
    return 'review'
  }
  if (nodeKeyValue.startsWith('N3_') || nodeKeyValue.includes('SCRIPT')) {
    return 'file'
  }
  return 'file'
}

const VIDEO_PROFILE_DEFAULTS: Omit<TaskDetailProfile, 'id' | 'submitMode' | 'showCaptureProgress'> = {
  hideDeliverable: true,
  hideHandshakeFields: true,
  hideWatchers: true,
  collapseComments: true,
  compactMetadata: true,
}

const TASK_DETAIL_PROFILE_IDS: TaskDetailProfileId[] = [
  'video_n1_capture',
  'video_n2_aggregate',
  'video_batch_root',
  'video_production_step',
  'video_production_multi',
  'video_production_platform',
  'video_capture_assign',
  'video_capture_schedule',
  'graph_manual',
  'legacy_task',
]

function readUiProfileOverride(metadata: Record<string, unknown>): TaskDetailProfileId | null {
  const value = metadata.ui_profile
  if (typeof value !== 'string') {
    return null
  }
  return TASK_DETAIL_PROFILE_IDS.includes(value as TaskDetailProfileId)
    ? (value as TaskDetailProfileId)
    : null
}

function profileFromOverride(
  profileId: TaskDetailProfileId,
  task: Task,
  metadata: Record<string, unknown>,
  currentUserId?: string | null,
): TaskDetailProfile {
  switch (profileId) {
    case 'video_batch_root':
      return {
        id: 'video_batch_root',
        submitMode: null,
        showCaptureProgress: true,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    case 'video_n2_aggregate':
      return {
        id: 'video_n2_aggregate',
        submitMode: null,
        showCaptureProgress: true,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    case 'video_n1_capture':
      return {
        id: 'video_n1_capture',
        submitMode: 'form',
        showCaptureProgress: false,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    case 'video_capture_assign':
      return {
        id: 'video_capture_assign',
        submitMode: 'form',
        showCaptureProgress: false,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    case 'video_capture_schedule':
      return {
        id: 'video_capture_schedule',
        submitMode: 'form',
        showCaptureProgress: false,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    case 'video_production_multi':
      return {
        id: 'video_production_multi',
        submitMode: 'file',
        showCaptureProgress: false,
        hideDeliverable: true,
        hideHandshakeFields: true,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: true,
      }
    case 'video_production_platform':
      return {
        id: 'video_production_platform',
        submitMode: 'file',
        showCaptureProgress: false,
        hideDeliverable: true,
        hideHandshakeFields: true,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: true,
      }
    case 'video_production_step': {
      const key = nodeKey(metadata)
      const submitMode = inferSubmitMode(key)
      return {
        id: 'video_production_step',
        submitMode,
        showCaptureProgress: false,
        hideDeliverable: submitMode === 'file',
        hideHandshakeFields: true,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: true,
      }
    }
    case 'graph_manual':
      return {
        id: 'graph_manual',
        submitMode: null,
        hideDeliverable: false,
        hideHandshakeFields: false,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: false,
        showCaptureProgress: false,
      }
    case 'legacy_task':
      return {
        id: 'legacy_task',
        submitMode: null,
        hideDeliverable: false,
        hideHandshakeFields: false,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: false,
        showCaptureProgress: false,
      }
    default:
      return profileFromOverride('legacy_task', task, metadata, currentUserId)
  }
}

export function resolveTaskDetailProfile(
  task: Task | null | undefined,
  options: ResolveTaskDetailProfileOptions = {},
): TaskDetailProfile {
  if (!task) {
    return {
      id: 'legacy_task',
      submitMode: null,
      hideDeliverable: false,
      hideHandshakeFields: false,
      hideWatchers: false,
      collapseComments: false,
      compactMetadata: false,
      showCaptureProgress: false,
    }
  }

  const metadata = readMetadata(task)
  const currentUserId = options.currentUserId ?? null
  const uiProfileOverride = readUiProfileOverride(metadata)
  if (uiProfileOverride) {
    return profileFromOverride(uiProfileOverride, task, metadata, currentUserId)
  }

  if (isGraphTemplateTask(task, metadata)) {
    const isRootBatch =
      metadata.workflow_graph_root_task === true && runKind(metadata) === 'batch'

    if (isRootBatch) {
      return {
        id: 'video_batch_root',
        submitMode: null,
        showCaptureProgress: true,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    }

    const key = nodeKey(metadata)

    if (isAggregateNode(key)) {
      return {
        id: 'video_n2_aggregate',
        submitMode: null,
        showCaptureProgress: true,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    }

    if (isCaptureNode(key) && task.assignee_id === currentUserId && task.status !== 'done') {
      return {
        id: 'video_n1_capture',
        submitMode: 'form',
        showCaptureProgress: false,
        ...VIDEO_PROFILE_DEFAULTS,
      }
    }

    if (key && !isCaptureNode(key) && !isAggregateNode(key)) {
      const submitMode = inferSubmitMode(key)
      return {
        id: 'video_production_step',
        submitMode,
        showCaptureProgress: false,
        hideDeliverable: submitMode === 'file',
        hideHandshakeFields: true,
        hideWatchers: false,
        collapseComments: false,
        compactMetadata: true,
      }
    }
  }

  if (isGraphHandshakeTask(task, metadata)) {
    return {
      id: 'graph_manual',
      submitMode: null,
      hideDeliverable: false,
      hideHandshakeFields: false,
      hideWatchers: false,
      collapseComments: false,
      compactMetadata: false,
      showCaptureProgress: false,
    }
  }

  return {
    id: 'legacy_task',
    submitMode: null,
    hideDeliverable: false,
    hideHandshakeFields: false,
    hideWatchers: false,
    collapseComments: false,
    compactMetadata: false,
    showCaptureProgress: false,
  }
}

export function isVideoWorkflowProfile(profile: TaskDetailProfile): boolean {
  return profile.id.startsWith('video_')
}

export function shouldShowLegacyStatusActions(
  profile: TaskDetailProfile,
  taskStatus: TaskStatus,
): boolean {
  if (profile.id === 'graph_manual' || profile.id === 'legacy_task') {
    return true
  }
  if (
    (profile.id === 'video_production_step'
      || profile.id === 'video_production_multi'
      || profile.id === 'video_production_platform')
    && taskStatus !== 'review'
  ) {
    return profile.submitMode !== 'file'
  }
  if (profile.id === 'video_capture_assign' || profile.id === 'video_capture_schedule') {
    return false
  }
  return false
}
