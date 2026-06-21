import { expect, type Page, type Route } from '@playwright/test'

import {
  defaultTaskCenterPagination,
  fulfillJson,
  fulfillTaskCenterListPage,
  fulfillTasksListGet,
  getApiPath,
  getApiPathname,
  isExactApiPath,
} from './mock-api-helpers.ts'

const adminUser = {
  id: 'user-admin',
  email: 'admin@example.com',
  role: 'admin',
  status: 'active',
  last_login_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const copyLeadUser = {
  id: 'user-copy-lead',
  email: 'demo.video.copy.lead@example.com',
  role: 'employee',
  status: 'active',
  last_login_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const postLeadUser = {
  id: 'user-post-lead',
  email: 'demo.video.post.lead@example.com',
  role: 'employee',
  status: 'active',
  last_login_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const videoEditorUser = {
  id: 'user-video-editor',
  email: 'demo.video.editor@example.com',
  role: 'employee',
  status: 'active',
  last_login_at: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

export const VIDEO_DEMO_ACCOUNTS = {
  copyLead: copyLeadUser.email,
  copyA: 'demo.video.copy.a@example.com',
  copyB: 'demo.video.copy.b@example.com',
  copyC: 'demo.video.copy.c@example.com',
  postLead: postLeadUser.email,
  editor: videoEditorUser.email,
} as const

const editorUsers = [
  {
    id: 'user-editor-a',
    email: 'demo.video.copy.a@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-editor-b',
    email: 'demo.video.copy.b@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'user-editor-c',
    email: 'demo.video.copy.c@example.com',
    role: 'employee',
    status: 'active',
    last_login_at: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
]

const allDemoUsers = [copyLeadUser, postLeadUser, videoEditorUser, ...editorUsers, adminUser]

function resolveUserByEmail(email: string) {
  return allDemoUsers.find((user) => user.email === email) ?? copyLeadUser
}

function resolveUserById(userId: string) {
  return allDemoUsers.find((user) => user.id === userId) ?? copyLeadUser
}

const batchTemplateId = 'tpl-batch-1'
const productionTemplateId = 'tpl-production-1'
const batchInstanceId = 'batch-inst-1'
const rootTaskId = 'task-root-batch'
const n2TaskId = 'task-n2-aggregate'

export const videoMockState = {
  batchInstanceId,
  rootTaskId,
  topicIds: ['topic-a', 'topic-b', 'topic-c'] as string[],
  childInstanceIds: [] as string[],
  childRootTaskIds: [] as string[],
  captureSubmitted: new Set<string>(),
  forkedTopics: {} as Record<string, string>,
  finalized: false,
  forked: false,
  /** When false, `/auth/refresh` returns 401 so the login form is shown (guestOnly redirect). */
  sessionActive: false,
  rejectedTopicIds: new Set<string>(),
  rejectedCaptureTaskIds: new Set<string>(),
  currentUserId: copyLeadUser.id,
  runLabel: 'E2E多账号批次',
  aggregateMode: 'batch' as 'batch' | 'streaming',
  productionTasks: [] as Array<{
    childInstanceId: string
    scriptTaskId: string
    reviewTaskId: string
    voUploadTaskId: string
    editAssignTaskId: string
    editWorkTaskId: string
    editReviewTaskId: string
    platformUploadTaskId: string
    scheduleTaskId: string
    postCloseTaskId: string
    copyCosignTaskId: string
    authorId: string
    deliverableDone: boolean
    reviewDone: boolean
    voUploadDone: boolean
    editAssignDone: boolean
    editWorkDone: boolean
    editReviewDone: boolean
    platformUploadDone: boolean
    scheduleDone: boolean
    postCloseDone: boolean
    copyCosignDone: boolean
    archived: boolean
    editAssigneeId: string | null
  }>,
}

export function resetVideoMockForMultiAccount(runLabel: string): void {
  videoMockState.captureSubmitted.clear()
  videoMockState.forkedTopics = {}
  videoMockState.rejectedTopicIds.clear()
  videoMockState.rejectedCaptureTaskIds.clear()
  videoMockState.finalized = false
  videoMockState.forked = false
  videoMockState.childInstanceIds = []
  videoMockState.childRootTaskIds = []
  videoMockState.productionTasks = []
  videoMockState.runLabel = runLabel
  videoMockState.aggregateMode = 'batch'
  videoMockState.sessionActive = false
  videoMockState.currentUserId = copyLeadUser.id
}

function buildCaptureTask(editorId: string, taskId: string) {
  const editor = editorUsers.find((user) => user.id === editorId) ?? editorUsers[0]
  const submitted = videoMockState.captureSubmitted.has(taskId)
  const rejected = videoMockState.rejectedCaptureTaskIds.has(taskId)
  return {
    id: taskId,
    title: '选题会（批次） / 提交选题',
    description: null,
    creator_id: adminUser.id,
    // E2E 以管理员登录，采集面板仅对当前 assignee 可见
    assignee_id: editor.id,
    department_id: 'dept-video-copy',
    status: rejected ? 'doing' : submitted ? 'done' : 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T08:00:00Z',
    completed_at: submitted && !rejected ? '2025-05-01T09:00:00Z' : null,
    parent_task_id: rootTaskId,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: batchInstanceId,
      workflow_node_instance_id: `ni-capture-${editorId}`,
      template_id: batchTemplateId,
      template_code: 'topic_meeting_batch_v1',
      template_node_key: 'N1_PROPOSE',
      template_node_instance_key: editorId,
      run_kind: 'batch',
      ...(rejected
        ? {
            latest_rework_reason: 'E2E mock reject',
            latest_capture_state: 'rejected',
          }
        : {}),
    },
    created_at: '2025-05-01T08:00:00Z',
    updated_at: '2025-05-01T08:00:00Z',
  }
}

function getCaptureTasks() {
  return [
    buildCaptureTask('user-editor-a', 'task-capture-a'),
    buildCaptureTask('user-editor-b', 'task-capture-b'),
    buildCaptureTask('user-editor-c', 'task-capture-c'),
  ]
}

type VideoMockTask = ReturnType<typeof buildRootTask>

function toTaskCenterInboxItem(task: VideoMockTask) {
  const handler = resolveUserById(task.assignee_id)
  return {
    task_id: task.id,
    title: task.title,
    priority: task.priority,
    status: task.status,
    due_date: task.due_date,
    department_name: '视频文案部',
    current_stage_label: '待处理',
    current_handler_label: handler.email,
  }
}

function toTaskCenterTrackingItem(task: VideoMockTask, currentStageLabel: string) {
  return {
    task_id: task.id,
    title: task.title,
    priority: task.priority,
    status: task.status,
    due_date: task.due_date,
    department_name: '视频文案部',
    relation_types: ['发布人'],
    current_stage_label: currentStageLabel,
    current_handler_label: adminUser.email,
  }
}

function buildProductionScriptTask(scriptTaskId: string, authorId: string, topicLabel: string, childInstanceId = 'child-inst-1') {
  const author = resolveUserById(authorId)
  return {
    id: scriptTaskId,
    title: `单题制作 / 撰写脚本 ${topicLabel}`,
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: author.id,
    department_id: 'dept-video-copy',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T11:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-script-${scriptTaskId}`,
      template_node_key: 'N3_SCRIPT_WRITE',
      run_kind: 'production',
    },
    created_at: '2025-05-01T11:00:00Z',
    updated_at: '2025-05-01T11:00:00Z',
  }
}

function buildProductionReviewTask(reviewTaskId: string, topicLabel: string, childInstanceId = 'child-inst-1') {
  return {
    id: reviewTaskId,
    title: `单题制作 / 脚本审核 ${topicLabel}`,
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: copyLeadUser.id,
    department_id: 'dept-video-copy',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T12:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-review-${reviewTaskId}`,
      template_node_key: 'N4_SCRIPT_REVIEW',
      run_kind: 'production',
    },
    created_at: '2025-05-01T12:00:00Z',
    updated_at: '2025-05-01T12:00:00Z',
  }
}

function buildProductionVoUploadTask(
  voUploadTaskId: string,
  authorId: string,
  topicLabel: string,
  childInstanceId: string,
) {
  return {
    id: voUploadTaskId,
    title: `单题制作 / 配音审核并上传 ${topicLabel}`,
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: authorId,
    department_id: 'dept-video-copy',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T13:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-vo-upload-${voUploadTaskId}`,
      template_node_key: 'N5_VO_UPLOAD',
      run_kind: 'production',
      ui_profile: 'video_production_multi',
    },
    created_at: '2025-05-01T13:00:00Z',
    updated_at: '2025-05-01T13:00:00Z',
  }
}

function buildProductionEditAssignTask(editAssignTaskId: string, topicLabel: string, childInstanceId: string) {
  return {
    id: editAssignTaskId,
    title: `单题制作 / 指派剪辑 ${topicLabel}`,
    description: null,
    creator_id: postLeadUser.id,
    assignee_id: postLeadUser.id,
    department_id: 'dept-video-post',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T14:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-edit-assign-${editAssignTaskId}`,
      template_node_key: 'N7_EDIT_ASSIGN',
      run_kind: 'production',
      ui_profile: 'video_capture_assign',
    },
    created_at: '2025-05-01T14:00:00Z',
    updated_at: '2025-05-01T14:00:00Z',
  }
}

function buildProductionEditWorkTask(editWorkTaskId: string, assigneeId: string, topicLabel: string, childInstanceId: string) {
  const assignee = resolveUserById(assigneeId)
  return {
    id: editWorkTaskId,
    title: `单题制作 / 粗剪制作 ${topicLabel}`,
    description: null,
    creator_id: postLeadUser.id,
    assignee_id: assignee.id,
    department_id: 'dept-video-post',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T15:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-edit-work-${editWorkTaskId}`,
      template_node_key: 'N8_EDIT_WORK',
      run_kind: 'production',
    },
    created_at: '2025-05-01T15:00:00Z',
    updated_at: '2025-05-01T15:00:00Z',
  }
}

function buildProductionEditReviewTask(
  editReviewTaskId: string,
  authorId: string,
  topicLabel: string,
  childInstanceId: string,
) {
  return {
    id: editReviewTaskId,
    title: `单题制作 / 粗剪审核 ${topicLabel}`,
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: authorId,
    department_id: 'dept-video-copy',
    status: 'review',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T16:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-edit-review-${editReviewTaskId}`,
      template_node_key: 'N9_EDIT_REVIEW',
      run_kind: 'production',
    },
    created_at: '2025-05-01T16:00:00Z',
    updated_at: '2025-05-01T16:00:00Z',
  }
}

function buildProductionPlatformUploadTask(
  platformUploadTaskId: string,
  assigneeId: string,
  topicLabel: string,
  childInstanceId: string,
) {
  return {
    id: platformUploadTaskId,
    title: `单题制作 / 上传平台 ${topicLabel}`,
    description: null,
    creator_id: postLeadUser.id,
    assignee_id: assigneeId,
    department_id: 'dept-video-post',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T17:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-platform-${platformUploadTaskId}`,
      template_node_key: 'N10_UPLOAD',
      run_kind: 'production',
      ui_profile: 'video_production_platform',
    },
    created_at: '2025-05-01T17:00:00Z',
    updated_at: '2025-05-01T17:00:00Z',
  }
}

function buildProductionScheduleTask(
  scheduleTaskId: string,
  topicLabel: string,
  childInstanceId: string,
) {
  return {
    id: scheduleTaskId,
    title: `单题制作 / 排期发布 ${topicLabel}`,
    description: null,
    creator_id: postLeadUser.id,
    assignee_id: postLeadUser.id,
    department_id: 'dept-video-post',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T18:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-schedule-${scheduleTaskId}`,
      template_node_key: 'N11_SCHEDULE',
      run_kind: 'production',
      ui_profile: 'video_capture_schedule',
    },
    created_at: '2025-05-01T18:00:00Z',
    updated_at: '2025-05-01T18:00:00Z',
  }
}

function buildProductionCloseReviewTask(
  taskId: string,
  nodeKey: 'N12_CLOSE' | 'N12_COSIGN',
  titleSuffix: string,
  assigneeId: string,
  topicLabel: string,
  childInstanceId: string,
) {
  return {
    id: taskId,
    title: `单题制作 / ${titleSuffix} ${topicLabel}`,
    description: null,
    creator_id: postLeadUser.id,
    assignee_id: assigneeId,
    department_id: nodeKey === 'N12_CLOSE' ? 'dept-video-post' : 'dept-video-copy',
    status: 'review',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T19:00:00Z',
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: childInstanceId,
      workflow_node_instance_id: `ni-${nodeKey.toLowerCase()}-${taskId}`,
      template_node_key: nodeKey,
      run_kind: 'production',
    },
    created_at: '2025-05-01T19:00:00Z',
    updated_at: '2025-05-01T19:00:00Z',
  }
}

function resolveProductionCurrentNodeKey(
  production: (typeof videoMockState.productionTasks)[number] | undefined,
): string {
  if (!production) {
    return 'N3_SCRIPT_WRITE'
  }
  if (production.archived || production.copyCosignDone) {
    return 'N12_COSIGN'
  }
  if (production.postCloseDone) {
    return 'N12_COSIGN'
  }
  if (production.scheduleDone) {
    return 'N12_CLOSE'
  }
  if (production.platformUploadDone) {
    return 'N11_SCHEDULE'
  }
  if (production.editReviewDone) {
    return 'N10_UPLOAD'
  }
  if (production.editWorkDone) {
    return 'N9_EDIT_REVIEW'
  }
  if (production.editAssignDone) {
    return 'N8_EDIT_WORK'
  }
  if (production.voUploadDone) {
    return 'N7_EDIT_ASSIGN'
  }
  if (production.reviewDone) {
    return 'N5_VO_UPLOAD'
  }
  if (production.deliverableDone) {
    return 'N4_SCRIPT_REVIEW'
  }
  return 'N3_SCRIPT_WRITE'
}

function createProductionEntry(index: number, childId: string, authorId: string) {
  const suffix = index + 1
  return {
    childInstanceId: childId,
    scriptTaskId: `task-n3-${suffix}`,
    reviewTaskId: `task-n4-${suffix}`,
    voUploadTaskId: `task-n5-${suffix}`,
    editAssignTaskId: `task-n7-${suffix}`,
    editWorkTaskId: `task-n8-${suffix}`,
    editReviewTaskId: `task-n9-${suffix}`,
    platformUploadTaskId: `task-n10-${suffix}`,
    scheduleTaskId: `task-n11-${suffix}`,
    postCloseTaskId: `task-n12-close-${suffix}`,
    copyCosignTaskId: `task-n12-cosign-${suffix}`,
    authorId,
    deliverableDone: false,
    reviewDone: false,
    voUploadDone: false,
    editAssignDone: false,
    editWorkDone: false,
    editReviewDone: false,
    platformUploadDone: false,
    scheduleDone: false,
    postCloseDone: false,
    copyCosignDone: false,
    archived: false,
    editAssigneeId: null as string | null,
  }
}

function findProductionByTaskId(taskId: string) {
  return videoMockState.productionTasks.find(
    (item) =>
      item.scriptTaskId === taskId
      || item.reviewTaskId === taskId
      || item.voUploadTaskId === taskId
      || item.editAssignTaskId === taskId
      || item.editWorkTaskId === taskId
      || item.editReviewTaskId === taskId
      || item.platformUploadTaskId === taskId
      || item.scheduleTaskId === taskId
      || item.postCloseTaskId === taskId
      || item.copyCosignTaskId === taskId,
  )
}

function buildTaskCenterSnapshot() {
  const root = buildRootTask()
  const aggregate = buildAggregateTask()
  const currentUserId = videoMockState.currentUserId
  const tracking = [
    toTaskCenterTrackingItem(root, '批次运行'),
    toTaskCenterTrackingItem(aggregate, '汇总派发'),
    ...getCaptureTasks().map((task) => toTaskCenterTrackingItem(task, '提交选题')),
  ]
  for (const [index, childTaskId] of videoMockState.childRootTaskIds.entries()) {
    tracking.push(
      toTaskCenterTrackingItem(
        {
          id: childTaskId,
          title: `单题制作 / 选题 ${String.fromCharCode(65 + index)}`,
          priority: 'medium',
          status: 'doing',
          due_date: null,
        } as VideoMockTask,
        '脚本撰写',
      ),
    )
  }

  const inboxTasks: VideoMockTask[] = getCaptureTasks().filter(
    (task) => !videoMockState.captureSubmitted.has(task.id) && task.assignee_id === currentUserId,
  )
  for (const production of videoMockState.productionTasks) {
    const label = production.scriptTaskId
    if (!production.deliverableDone && production.authorId === currentUserId) {
      inboxTasks.push(
        buildProductionScriptTask(
          production.scriptTaskId,
          production.authorId,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (!production.reviewDone && copyLeadUser.id === currentUserId) {
      inboxTasks.push(buildProductionReviewTask(production.reviewTaskId, label, production.childInstanceId))
    }
    if (production.reviewDone && !production.voUploadDone && production.authorId === currentUserId) {
      inboxTasks.push(
        buildProductionVoUploadTask(
          production.voUploadTaskId,
          production.authorId,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (production.voUploadDone && !production.editAssignDone && postLeadUser.id === currentUserId) {
      inboxTasks.push(buildProductionEditAssignTask(production.editAssignTaskId, label, production.childInstanceId))
    }
    if (production.editAssignDone && !production.editWorkDone && production.editAssigneeId === currentUserId) {
      inboxTasks.push(
        buildProductionEditWorkTask(
          production.editWorkTaskId,
          production.editAssigneeId,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (production.editWorkDone && !production.editReviewDone && production.authorId === currentUserId) {
      inboxTasks.push(
        buildProductionEditReviewTask(
          production.editReviewTaskId,
          production.authorId,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (
      production.editReviewDone
      && !production.platformUploadDone
      && production.editAssigneeId === currentUserId
    ) {
      inboxTasks.push(
        buildProductionPlatformUploadTask(
          production.platformUploadTaskId,
          production.editAssigneeId,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (production.platformUploadDone && !production.scheduleDone && postLeadUser.id === currentUserId) {
      inboxTasks.push(
        buildProductionScheduleTask(production.scheduleTaskId, label, production.childInstanceId),
      )
    }
    if (production.scheduleDone && !production.postCloseDone && postLeadUser.id === currentUserId) {
      inboxTasks.push(
        buildProductionCloseReviewTask(
          production.postCloseTaskId,
          'N12_CLOSE',
          '结案确认',
          postLeadUser.id,
          label,
          production.childInstanceId,
        ),
      )
    }
    if (production.postCloseDone && !production.copyCosignDone && copyLeadUser.id === currentUserId) {
      inboxTasks.push(
        buildProductionCloseReviewTask(
          production.copyCosignTaskId,
          'N12_COSIGN',
          '文案会签归档',
          copyLeadUser.id,
          label,
          production.childInstanceId,
        ),
      )
    }
  }

  const currentUser = resolveUserById(videoMockState.currentUserId)
  const canPublishOrgTask =
    currentUser.id === copyLeadUser.id || currentUser.role === 'admin' || currentUser.role === 'hr'
  return {
    permissions: {
      can_manage_templates: currentUser.role === 'admin' || currentUser.role === 'hr',
      can_publish_task: canPublishOrgTask,
    },
    template_summaries: [],
    publish_department_options: [{ id: 'dept-video-copy', label: '视频文案部' }],
    publish_user_options: editorUsers.map((user) => ({
      user_id: user.id,
      email: user.email,
      real_name: user.email,
      department_id: 'dept-video-copy',
      department_name: '视频文案部',
      label: user.email,
    })),
    task_inbox: inboxTasks.map(toTaskCenterInboxItem),
    task_tracking: tracking,
    task_history: [],
    task_memos: [],
  }
}

function buildAggregateTask() {
  return {
    id: n2TaskId,
    title: '选题会（批次） / 汇总派发',
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: copyLeadUser.id,
    department_id: 'dept-video-copy',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: rootTaskId,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: batchInstanceId,
      workflow_node_instance_id: 'ni-aggregate',
      template_id: batchTemplateId,
      template_code: 'topic_meeting_batch_v1',
      template_node_key: 'N2_AGGREGATE',
      run_kind: 'batch',
    },
    created_at: '2025-05-01T08:00:00Z',
    updated_at: '2025-05-01T08:00:00Z',
  }
}

function buildRootTask() {
  return {
    id: rootTaskId,
    title: `选题会（批次） / ${videoMockState.runLabel}`,
    description: null,
    creator_id: copyLeadUser.id,
    assignee_id: copyLeadUser.id,
    department_id: 'dept-video-copy',
    status: 'doing',
    priority: 'medium',
    due_date: null,
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'template',
    extra_metadata: {
      workflow_graph_instance_id: batchInstanceId,
      workflow_graph_root_task: true,
      template_id: batchTemplateId,
      template_code: 'topic_meeting_batch_v1',
      run_kind: 'batch',
    },
    created_at: '2025-05-01T08:00:00Z',
    updated_at: '2025-05-01T08:00:00Z',
  }
}

function buildBatchGraphInstance() {
  return {
    id: batchInstanceId,
    template_id: batchTemplateId,
    initiator_user_id: adminUser.id,
    department_id: 'dept-video-copy',
    source_type: 'template',
    status: 'active',
    current_node_key: videoMockState.finalized ? 'N2_AGGREGATE' : 'N1_PROPOSE',
    run_label: videoMockState.runLabel,
    parent_instance_id: null,
    context: {
      run_kind: 'batch',
      aggregate_mode: videoMockState.aggregateMode,
      run_label: videoMockState.runLabel,
      manager_user_id: copyLeadUser.id,
      inputs: { theme: 'W10 E2E', manager_user_id: copyLeadUser.id },
      root_task_id: rootTaskId,
      fork_status: videoMockState.forked ? 'completed' : 'pending',
      forked_child_instance_ids: videoMockState.childInstanceIds,
      forked_topics: { ...videoMockState.forkedTopics },
      schema_snapshot: {
        aggregate_mode: videoMockState.aggregateMode,
        nodes: {
          N1_PROPOSE: {
            capture_schema: {
              mode: 'row_table',
              min_rows: 1,
              max_rows: 5,
              columns: [
                { key: 'title', label: '标题', type: 'text', required: true },
                { key: 'content', label: '内容', type: 'textarea' },
              ],
            },
          },
          N2_AGGREGATE: {
            aggregate_schema: {
              mode: 'submission_matrix',
              source_node_key: 'N1_PROPOSE',
              row_id_field: 'topic_id',
            },
          },
        },
      },
    },
    context_version: 2,
    max_iterations: 5,
    completed_at: null,
    created_at: '2025-05-01T08:00:00Z',
    node_instances: [
      {
        id: 'ni-capture-a',
        instance_id: batchInstanceId,
        template_node_id: 'tn-n1',
        node_key: 'N1_PROPOSE',
        title: '提交选题',
        node_type: 'task',
        engine_state: videoMockState.captureSubmitted.has('task-capture-a') ? 'completed' : 'activated',
        business_state: 'doing',
        assignee_user_id: 'user-editor-a',
        iteration: 1,
        activated_at: '2025-05-01T08:00:00Z',
        completed_at: videoMockState.captureSubmitted.has('task-capture-a') ? '2025-05-01T09:00:00Z' : null,
        terminated_at: null,
        created_at: '2025-05-01T08:00:00Z',
      },
      {
        id: 'ni-aggregate',
        instance_id: batchInstanceId,
        template_node_id: 'tn-n2',
        node_key: 'N2_AGGREGATE',
        title: '汇总派发',
        node_type: 'task',
        engine_state: videoMockState.finalized ? 'completed' : 'pending',
        business_state: 'doing',
        assignee_user_id: adminUser.id,
        iteration: 1,
        activated_at: videoMockState.finalized ? '2025-05-01T10:00:00Z' : null,
        completed_at: videoMockState.finalized ? '2025-05-01T11:00:00Z' : null,
        terminated_at: null,
        created_at: '2025-05-01T08:00:00Z',
      },
    ],
    total_node_count: 4,
    completed_node_count: videoMockState.finalized ? 2 : videoMockState.captureSubmitted.size,
    active_node_count: 1,
    pending_node_count: 1,
    progress_percent: videoMockState.finalized ? 50 : 25,
  }
}

function buildChildGraphInstance(childId: string, topicTitle: string, rootTask: string) {
  const production = videoMockState.productionTasks.find((item) => item.childInstanceId === childId)
  const currentNodeKey = resolveProductionCurrentNodeKey(production)

  return {
    id: childId,
    template_id: productionTemplateId,
    initiator_user_id: adminUser.id,
    department_id: 'dept-video-copy',
    source_type: 'template',
    status: production?.archived ? 'completed' : 'active',
    current_node_key: currentNodeKey,
    run_label: topicTitle,
    parent_instance_id: batchInstanceId,
    context: {
      run_kind: 'production',
      topic_title: topicTitle,
      root_task_id: rootTask,
      script_author_id: production?.authorId ?? adminUser.id,
      edit_assignee_id: production?.editAssigneeId ?? null,
      archived: production?.archived ?? false,
      schema_snapshot: {
        nodes: {
          N3_SCRIPT_WRITE: {
            capture_schema: {
              mode: 'row_table',
              min_rows: 1,
              max_rows: 1,
              columns: [{ key: 'title', label: '脚本标题', type: 'text', required: true }],
            },
          },
          N7_EDIT_ASSIGN: {
            capture_schema: {
              mode: 'row_table',
              min_rows: 1,
              max_rows: 1,
              columns: [{ key: 'edit_assignee_id', label: '剪辑师', type: 'user', required: true }],
            },
            ui_profile: 'video_capture_assign',
          },
          N11_SCHEDULE: {
            capture_schema: {
              mode: 'row_table',
              min_rows: 1,
              max_rows: 1,
              columns: [
                { key: 'publish_at', label: '发布时间', type: 'datetime', required: true },
                { key: 'platform', label: '发布平台', type: 'text', required: true },
                { key: 'publish_title', label: '标题', type: 'text', required: true },
              ],
            },
            ui_profile: 'video_capture_schedule',
          },
        },
      },
    },
    context_version: production?.archived ? 8 : production?.copyCosignDone ? 7 : 1,
    max_iterations: 5,
    completed_at: production?.archived ? '2025-05-01T20:00:00Z' : null,
    created_at: '2025-05-01T11:00:00Z',
    node_instances: [
      {
        id: `ni-script-${childId}`,
        instance_id: childId,
        template_node_id: 'tn-n3',
        node_key: 'N3_SCRIPT_WRITE',
        title: '撰写脚本',
        node_type: 'task',
        engine_state: production?.deliverableDone ? 'completed' : 'activated',
        business_state: 'doing',
        assignee_user_id: production?.authorId ?? adminUser.id,
        iteration: 1,
        activated_at: '2025-05-01T11:00:00Z',
        completed_at: production?.deliverableDone ? '2025-05-01T12:00:00Z' : null,
        terminated_at: null,
        created_at: '2025-05-01T11:00:00Z',
      },
      ...(production?.voUploadDone
        ? [
            {
              id: `ni-edit-assign-${childId}`,
              instance_id: childId,
              template_node_id: 'tn-n7',
              node_key: 'N7_EDIT_ASSIGN',
              title: '指派剪辑',
              node_type: 'task',
              engine_state: production.editAssignDone ? 'completed' : 'activated',
              business_state: 'doing',
              assignee_user_id: postLeadUser.id,
              iteration: 1,
              activated_at: '2025-05-01T14:00:00Z',
              completed_at: production.editAssignDone ? '2025-05-01T15:00:00Z' : null,
              terminated_at: null,
              created_at: '2025-05-01T14:00:00Z',
            },
          ]
        : []),
    ],
    total_node_count: 6,
    completed_node_count: production?.editAssignDone ? 4 : production?.voUploadDone ? 3 : production?.reviewDone ? 2 : 0,
    active_node_count: 1,
    pending_node_count: 2,
    progress_percent: production?.editAssignDone ? 66 : production?.voUploadDone ? 50 : 33,
  }
}

async function buildAllMockTasks() {
  const allTasks = [buildRootTask(), buildAggregateTask(), ...getCaptureTasks()]
  if (videoMockState.childRootTaskIds.length > 0) {
    for (const [index, childTaskId] of videoMockState.childRootTaskIds.entries()) {
      allTasks.push({
        id: childTaskId,
        title: `单题制作 / 选题 ${String.fromCharCode(65 + index)}`,
        description: null,
        creator_id: adminUser.id,
        assignee_id: adminUser.id,
        department_id: 'dept-video-copy',
        status: 'doing',
        priority: 'medium',
        due_date: null,
        started_at: null,
        completed_at: null,
        parent_task_id: null,
        source_type: 'template',
        extra_metadata: {
          workflow_graph_instance_id: videoMockState.childInstanceIds[index],
          template_node_key: 'N3_SCRIPT_WRITE',
          run_kind: 'production',
        },
        created_at: '2025-05-01T11:00:00Z',
        updated_at: '2025-05-01T11:00:00Z',
      })
    }
  }
  return allTasks
}

export async function installWorkflowVideoMockApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const apiPath = getApiPath(request.url())
    const pathname = getApiPathname(apiPath)

    if (request.method() === 'GET' && apiPath === '/auth/bootstrap-status') {
      await fulfillJson(route, { bootstrap_required: false })
      return
    }

    if (request.method() === 'POST' && apiPath === '/auth/login') {
      const body = request.postDataJSON() as { email?: string }
      const user = resolveUserByEmail(body.email ?? copyLeadUser.email)
      videoMockState.sessionActive = true
      videoMockState.currentUserId = user.id
      await fulfillJson(route, { access_token: 'token', token_type: 'bearer', user })
      return
    }

    if (request.method() === 'POST' && apiPath === '/auth/refresh') {
      if (!videoMockState.sessionActive) {
        await fulfillJson(route, { detail: 'Not authenticated' }, 401)
        return
      }
      const user = resolveUserById(videoMockState.currentUserId)
      await fulfillJson(route, { access_token: 'token', token_type: 'bearer', user })
      return
    }

    if (request.method() === 'GET' && apiPath === '/auth/me') {
      if (!videoMockState.sessionActive) {
        await fulfillJson(route, { detail: 'Not authenticated' }, 401)
        return
      }
      await fulfillJson(route, resolveUserById(videoMockState.currentUserId))
      return
    }

    if (request.method() === 'GET' && apiPath === '/workflow-graph/managed-department-member-options') {
      await fulfillJson(route, [
        { id: copyLeadUser.id, email: copyLeadUser.email, display_name: '韩策' },
        { id: postLeadUser.id, email: postLeadUser.email, display_name: '季衡' },
        { id: videoEditorUser.id, email: videoEditorUser.email, display_name: '叶舟' },
        { id: editorUsers[0].id, email: editorUsers[0].email, display_name: '陆言' },
        { id: editorUsers[1].id, email: editorUsers[1].email, display_name: '宋遥' },
        { id: editorUsers[2].id, email: editorUsers[2].email, display_name: '程野' },
      ])
      return
    }

    if (request.method() === 'GET' && apiPath === '/workflow-graph/feature-flags') {
      await fulfillJson(route, {
        workflow_graph_engine_enabled: true,
        workflow_graph_template_engine_enabled: true,
        task_center_v2_enabled: true,
        workflow_wait_any_enabled: false,
        workflow_deep_rejection_enabled: false,
        legacy_task_template_instantiation_enabled: true,
      })
      return
    }

    if (request.method() === 'GET' && isExactApiPath(apiPath, '/workflow-graph/templates')) {
      await fulfillJson(route, [
        {
          id: batchTemplateId,
          code: 'topic_meeting_batch_v1',
          name: '选题会（批次）',
          status: 'active',
          version: 1,
          run_kind: 'batch',
          config: {
            run_kind: 'batch',
            launch_schema: {
              fields: [
                { key: 'theme', label: '征集主题', type: 'text', required: true },
                { key: 'manager_user_id', label: '负责人', type: 'user', required: true },
                { key: 'due_at', label: '截止', type: 'datetime' },
              ],
            },
            participant_policies: { copywriters: { type: 'department_members' } },
          },
        },
        {
          id: productionTemplateId,
          code: 'video_production_per_topic_v1',
          name: '单题视频制作',
          status: 'active',
          version: 1,
          run_kind: 'production',
          config: { run_kind: 'production', participant_policies: {} },
        },
      ])
      return
    }

    if (request.method() === 'GET' && apiPath === `/workflow-graph/templates/${batchTemplateId}`) {
      await fulfillJson(route, {
        id: batchTemplateId,
        code: 'topic_meeting_batch_v1',
        name: '选题会（批次）',
        status: 'active',
        version: 1,
        run_kind: 'batch',
        config: {},
        nodes: [
          { id: 'tn-n1', node_key: 'N1_PROPOSE', title: '提交选题', sort_order: 1 },
          { id: 'tn-n2', node_key: 'N2_AGGREGATE', title: '汇总派发', sort_order: 2 },
        ],
      })
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/templates/${batchTemplateId}/preview-participants`) {
      await fulfillJson(route, {
        policy_ref: 'copywriters',
        mode: 'subset',
        user_ids: editorUsers.map((user) => user.id),
        users: editorUsers.map((user) => ({
          id: user.id,
          email: user.email,
          display_name: user.email,
        })),
        snapshot: { mode: 'subset', user_ids: editorUsers.map((user) => user.id) },
      })
      return
    }

    if (request.method() === 'POST' && apiPath === '/auth/logout') {
      videoMockState.sessionActive = false
      await fulfillJson(route, {})
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/templates/${batchTemplateId}/runs`) {
      const body = (request.postDataJSON() ?? {}) as { run_label?: string; inputs?: { theme?: string } }
      if (body.run_label) {
        videoMockState.runLabel = body.run_label
      }
      await fulfillJson(route, {
        instance_id: batchInstanceId,
        root_task_id: rootTaskId,
        run_kind: 'batch',
        activated_task_count: 3,
        node_instance_count: 4,
        current_node_key: 'N1_PROPOSE',
      })
      return
    }

    if (
      request.method() === 'GET'
      && (apiPath === `/workflow-graph/instances/${batchInstanceId}/submissions`
        || apiPath.startsWith(`/workflow-graph/instances/${batchInstanceId}/submissions?`))
    ) {
      const submissions = getCaptureTasks().map((task) => {
        const topicIndex = getCaptureTasks().findIndex((capture) => capture.id === task.id)
        const editor = editorUsers[topicIndex] ?? editorUsers[0]
        const submitted = videoMockState.captureSubmitted.has(task.id)
        const topicId = videoMockState.topicIds[topicIndex]
        const topicRejected = topicId ? videoMockState.rejectedTopicIds.has(topicId) : false
        return {
          node_instance_id: task.extra_metadata.workflow_node_instance_id,
          node_key: 'N1_PROPOSE',
          instance_key: task.extra_metadata.template_node_instance_key,
          assignee_user_id: task.assignee_id,
          assignee_email: editor.email,
          assignee_display_name: editor.email,
          submitted_at: submitted && !topicRejected ? '2025-05-01T09:00:00Z' : null,
          topics:
            submitted && !topicRejected
              ? [
                  {
                    topic_id: topicId,
                    title: `选题 ${String.fromCharCode(65 + topicIndex)}`,
                    content: null,
                    reason: null,
                  },
                ]
              : [],
        }
      })
      await fulfillJson(route, { instance_id: batchInstanceId, node_key: 'N1_PROPOSE', submissions })
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/instances/${batchInstanceId}/reject-captures`) {
      const body = request.postDataJSON() as {
        rejections?: Array<{ topic_id?: string; reason?: string }>
      }
      const captureTaskIds = ['task-capture-a', 'task-capture-b', 'task-capture-c']
      for (const rejection of body.rejections ?? []) {
        const topicId = rejection.topic_id
        if (!topicId) {
          continue
        }
        videoMockState.rejectedTopicIds.add(topicId)
        const topicIndex = videoMockState.topicIds.indexOf(topicId)
        if (topicIndex >= 0) {
          const taskId = captureTaskIds[topicIndex]
          videoMockState.captureSubmitted.delete(taskId)
          videoMockState.rejectedCaptureTaskIds.add(taskId)
        }
      }
      await fulfillJson(route, {
        instance_id: batchInstanceId,
        reopened_count: body.rejections?.length ?? 0,
        reopened_instance_keys: [],
      })
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/instances/${batchInstanceId}/dispatch-topic`) {
      const body = request.postDataJSON() as {
        topic_id?: string
        title?: string
        script_writer_user_id?: string
      }
      const topicId = body.topic_id ?? ''
      if (topicId && videoMockState.forkedTopics[topicId]) {
        await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: '该选题已派发制作，不可重复。' }) })
        return
      }

      const topicIndex = Math.max(0, videoMockState.topicIds.indexOf(topicId))
      const childId = `child-inst-dispatch-${topicIndex + 1}`
      const childTaskId = `task-child-dispatch-${topicIndex + 1}`
      const authorId = body.script_writer_user_id ?? editorUsers[topicIndex]?.id ?? editorUsers[0].id

      videoMockState.forked = true
      videoMockState.forkedTopics[topicId] = childId
      if (!videoMockState.childInstanceIds.includes(childId)) {
        videoMockState.childInstanceIds.push(childId)
        videoMockState.childRootTaskIds.push(childTaskId)
        videoMockState.productionTasks.push(createProductionEntry(topicIndex, childId, authorId))
      }

      await fulfillJson(route, {
        instance_id: batchInstanceId,
        child_instance_id: childId,
        fork_status: 'partial',
        message: '已指派并启动制作子 Run。',
      })
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/instances/${batchInstanceId}/finalize-topics`) {
      videoMockState.finalized = true
      videoMockState.forked = true
      const body = request.postDataJSON() as { approved_topics: Array<{ topic_id: string; title: string }> }
      videoMockState.childInstanceIds = []
      videoMockState.childRootTaskIds = []
      videoMockState.productionTasks = []
      for (const [index, topic] of body.approved_topics.entries()) {
        const childId = `child-inst-${index + 1}`
        const childTaskId = `task-child-${index + 1}`
        const authorId = editorUsers[index]?.id ?? editorUsers[0].id
        videoMockState.childInstanceIds.push(childId)
        videoMockState.childRootTaskIds.push(childTaskId)
        videoMockState.productionTasks.push(createProductionEntry(index, childId, authorId))
      }
      await fulfillJson(route, {
        instance_id: batchInstanceId,
        approved_count: body.approved_topics.length,
        fork_status: 'completed',
        fork_deferred: false,
        child_instance_ids: videoMockState.childInstanceIds,
      })
      return
    }

    if (request.method() === 'GET' && apiPath === `/workflow-graph/instances/${batchInstanceId}/children`) {
      const children = videoMockState.childInstanceIds
        .map((childId, index) =>
          buildChildGraphInstance(childId, `选题 ${String.fromCharCode(65 + index)}`, videoMockState.childRootTaskIds[index] ?? ''),
        )
        .filter((child) => {
          const production = videoMockState.productionTasks.find((item) => item.childInstanceId === child.id)
          return !production?.archived
        })
      await fulfillJson(route, children)
      return
    }

    if (request.method() === 'GET' && isExactApiPath(apiPath, `/workflow-graph/instances/${batchInstanceId}/events`)) {
      const items: Array<Record<string, unknown>> = [
        {
          id: 'evt-1',
          instance_id: batchInstanceId,
          event_type: 'run_instantiated',
          actor_user_id: adminUser.id,
          payload: {},
          created_at: '2025-05-01T08:00:00Z',
        },
      ]
      let seq = 2
      for (const taskId of videoMockState.captureSubmitted) {
        items.push({
          id: `evt-${seq++}`,
          instance_id: batchInstanceId,
          event_type: 'capture_submitted',
          actor_user_id: adminUser.id,
          payload: { task_id: taskId },
          created_at: '2025-05-01T09:00:00Z',
        })
      }
      if (videoMockState.rejectedTopicIds.size > 0) {
        items.push({
          id: `evt-${seq++}`,
          instance_id: batchInstanceId,
          event_type: 'capture_rejected',
          actor_user_id: adminUser.id,
          payload: { topic_ids: [...videoMockState.rejectedTopicIds] },
          created_at: '2025-05-01T09:30:00Z',
        })
      }
      if (videoMockState.finalized) {
        items.push({
          id: `evt-${seq++}`,
          instance_id: batchInstanceId,
          event_type: 'aggregate_confirmed',
          actor_user_id: adminUser.id,
          payload: {},
          created_at: '2025-05-01T10:00:00Z',
        })
        items.push({
          id: `evt-${seq++}`,
          instance_id: batchInstanceId,
          event_type: 'production_run_forked',
          actor_user_id: adminUser.id,
          payload: { child_count: videoMockState.childInstanceIds.length },
          created_at: '2025-05-01T11:00:00Z',
        })
      }
      await fulfillJson(route, {
        instance_id: batchInstanceId,
        items,
        total: items.length,
        limit: 20,
        offset: 0,
      })
      return
    }

    if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+$/.test(pathname)) {
      const instanceId = pathname.split('/').filter(Boolean).pop()
      if (instanceId?.startsWith('child-inst-')) {
        const index = videoMockState.childInstanceIds.indexOf(instanceId)
        await fulfillJson(
          route,
          buildChildGraphInstance(
            instanceId,
            `选题 ${String.fromCharCode(65 + index)}`,
            videoMockState.childRootTaskIds[index] ?? '',
          ),
        )
        return
      }
      await fulfillJson(route, buildBatchGraphInstance())
      return
    }

    if (request.method() === 'POST' && /^\/workflow-graph\/tasks\/[^/]+\/submit-capture$/.test(pathname)) {
      const taskId = pathname.split('/').filter(Boolean)[2] ?? ''
      const production = findProductionByTaskId(taskId)
      if (production && production.editAssignTaskId === taskId) {
        const body = request.postDataJSON() as { topics?: Array<{ edit_assignee_id?: string }> }
        const editAssigneeId = body.topics?.[0]?.edit_assignee_id ?? videoEditorUser.id
        production.editAssignDone = true
        production.editAssigneeId = editAssigneeId
        await fulfillJson(route, {
          task_id: taskId,
          node_instance_id: `ni-edit-assign-${production.childInstanceId}`,
          topic_count: 1,
          topics: [{ edit_assignee_id: editAssigneeId }],
        })
        return
      }
      if (production && production.scheduleTaskId === taskId) {
        production.scheduleDone = true
        await fulfillJson(route, {
          task_id: taskId,
          node_instance_id: `ni-schedule-${production.childInstanceId}`,
          topic_count: 1,
          topics: [{ publish_at: '2025-06-01T10:00:00Z', platform: '抖音', publish_title: 'E2E 标题' }],
        })
        return
      }
      videoMockState.captureSubmitted.add(taskId)
      const topicIndex = getCaptureTasks().findIndex((task) => task.id === taskId)
      await fulfillJson(route, {
        task_id: taskId,
        node_instance_id: `ni-capture-${getCaptureTasks()[topicIndex]?.assignee_id ?? 'a'}`,
        topic_count: 1,
        topics: [{ topic_id: videoMockState.topicIds[topicIndex], title: `选题 ${String.fromCharCode(65 + topicIndex)}` }],
      })
      return
    }

    if (request.method() === 'GET' && apiPath === '/task-center') {
      const snapshot = buildTaskCenterSnapshot()
      await fulfillJson(route, {
        ...snapshot,
        inbox_pagination: defaultTaskCenterPagination,
        tracking_pagination: defaultTaskCenterPagination,
        history_pagination: defaultTaskCenterPagination,
      })
      return
    }

    if (request.method() === 'GET') {
      const snapshot = buildTaskCenterSnapshot()
      if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/inbox', snapshot.task_inbox)) {
        return
      }
      if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/tracking', snapshot.task_tracking)) {
        return
      }
      if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/history', snapshot.task_history)) {
        return
      }
    }

    if (request.method() === 'GET' && (await fulfillTasksListGet(route, apiPath, await buildAllMockTasks()))) {
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/views/board') {
      await fulfillJson(route, [
        { status: 'todo', tasks: [] },
        { status: 'doing', tasks: getCaptureTasks() },
        { status: 'review', tasks: [] },
        { status: 'done', tasks: [] },
      ])
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/views/gantt') {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && apiPath === '/departments') {
      await fulfillJson(route, [
        {
          id: 'dept-video-copy',
          name: '视频文案部',
          code: 'video-copywriting',
          parent_id: null,
          manager_id: adminUser.id,
          sort_order: 1,
          is_active: true,
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
        },
      ])
      return
    }

    if (request.method() === 'GET' && apiPath === '/task-templates') {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && apiPath === '/task-templates/schedules/list') {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && apiPath === '/users') {
      await fulfillJson(route, [copyLeadUser, ...editorUsers, adminUser])
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/messages')) {
      await fulfillJson(route, { items: [], total_count: 0, filtered_count: 0, unread_count: 0, unacknowledged_count: 0, source_counts: [] })
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/stats/summary') {
      await fulfillJson(route, {
        total_tasks: 6,
        completed_tasks: 1,
        completion_rate: 0.16,
        overdue_tasks: 0,
        overdue_rate: 0,
        tasks_by_status: { todo: 0, doing: 5, review: 0, done: 1 },
      })
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/stats/workload') {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/activity$/.test(pathname)) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/watchers$/.test(pathname)) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'POST' && apiPath === '/attachments') {
      await fulfillJson(route, {
        id: `att-${Date.now()}`,
        filename: 'script.docx',
        content_type: 'application/octet-stream',
        size_bytes: 1024,
        target_type: 'task',
        target_id: 'task-mock',
        visibility: 'private',
        relation: 'deliverable',
        created_at: '2025-05-01T11:00:00Z',
      })
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/attachments')) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'POST' && /^\/tasks\/[^/]+\/deliverable$/.test(pathname)) {
      const taskId = apiPath.split('/').filter(Boolean)[1] ?? ''
      const production = findProductionByTaskId(taskId)
      if (production) {
        if (production.scriptTaskId === taskId) {
          production.deliverableDone = true
        } else if (production.voUploadTaskId === taskId) {
          production.voUploadDone = true
        } else if (production.editWorkTaskId === taskId) {
          production.editWorkDone = true
        } else if (production.platformUploadTaskId === taskId) {
          production.platformUploadDone = true
        }
      }
      await fulfillJson(route, { id: taskId, status: 'done' })
      return
    }

    if (
      request.method() === 'POST'
      && (/^\/tasks\/[^/]+\/review$/.test(pathname) || /^\/tasks\/[^/]+\/deliverable\/review$/.test(pathname))
    ) {
      const taskId = apiPath.split('/').filter(Boolean)[1] ?? ''
      const production = findProductionByTaskId(taskId)
      if (production) {
        if (production.reviewTaskId === taskId) {
          production.reviewDone = true
        } else if (production.editReviewTaskId === taskId) {
          production.editReviewDone = true
        } else if (production.postCloseTaskId === taskId) {
          production.postCloseDone = true
        } else if (production.copyCosignTaskId === taskId) {
          production.copyCosignDone = true
          production.archived = true
        }
      }
      await fulfillJson(route, { id: taskId, status: 'done' })
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+$/.test(pathname)) {
      const segments = pathname.split('/').filter(Boolean)
      const taskId = segments[1]
      let task = [buildRootTask(), buildAggregateTask(), ...getCaptureTasks()].find((item) => item.id === taskId)
      const production = findProductionByTaskId(taskId ?? '')
      if (!task && production) {
        const label = production.scriptTaskId
        if (production.scriptTaskId === taskId) {
          task = buildProductionScriptTask(production.scriptTaskId, production.authorId, label, production.childInstanceId)
        } else if (production.reviewTaskId === taskId) {
          task = buildProductionReviewTask(production.reviewTaskId, label, production.childInstanceId)
        } else if (production.voUploadTaskId === taskId) {
          task = buildProductionVoUploadTask(
            production.voUploadTaskId,
            production.authorId,
            label,
            production.childInstanceId,
          )
        } else if (production.editAssignTaskId === taskId) {
          task = buildProductionEditAssignTask(production.editAssignTaskId, label, production.childInstanceId)
        } else if (production.editWorkTaskId === taskId) {
          task = buildProductionEditWorkTask(
            production.editWorkTaskId,
            production.editAssigneeId ?? videoEditorUser.id,
            label,
            production.childInstanceId,
          )
        } else if (production.editReviewTaskId === taskId) {
          task = buildProductionEditReviewTask(
            production.editReviewTaskId,
            production.authorId,
            label,
            production.childInstanceId,
          )
        } else if (production.platformUploadTaskId === taskId) {
          task = buildProductionPlatformUploadTask(
            production.platformUploadTaskId,
            production.editAssigneeId ?? videoEditorUser.id,
            label,
            production.childInstanceId,
          )
        } else if (production.scheduleTaskId === taskId) {
          task = buildProductionScheduleTask(production.scheduleTaskId, label, production.childInstanceId)
        } else if (production.postCloseTaskId === taskId) {
          task = buildProductionCloseReviewTask(
            production.postCloseTaskId,
            'N12_CLOSE',
            '结案确认',
            postLeadUser.id,
            label,
            production.childInstanceId,
          )
        } else if (production.copyCosignTaskId === taskId) {
          task = buildProductionCloseReviewTask(
            production.copyCosignTaskId,
            'N12_COSIGN',
            '文案会签归档',
            copyLeadUser.id,
            label,
            production.childInstanceId,
          )
        }
      }
      if (!task && taskId?.startsWith('task-child-')) {
        const index = videoMockState.childRootTaskIds.indexOf(taskId)
        task = {
          id: taskId,
          title: `单题制作 / 选题 ${String.fromCharCode(65 + index)}`,
          description: null,
          creator_id: adminUser.id,
          assignee_id: adminUser.id,
          department_id: 'dept-video-copy',
          status: 'doing',
          priority: 'medium',
          due_date: null,
          started_at: null,
          completed_at: null,
          parent_task_id: null,
          source_type: 'template',
          extra_metadata: {
            workflow_graph_instance_id: videoMockState.childInstanceIds[index],
            workflow_node_instance_id: `ni-script-child-inst-${index + 1}`,
            template_node_key: 'N3_SCRIPT_WRITE',
            run_kind: 'production',
          },
          created_at: '2025-05-01T11:00:00Z',
          updated_at: '2025-05-01T11:00:00Z',
        }
      }
      if (task) {
        await fulfillJson(route, task)
        return
      }
    }

    await fulfillJson(route, { detail: `unhandled workflow-video mock: ${request.method()} ${apiPath}` }, 404)
  })
}

export async function loginAs(page: Page, email: string, password = 'secret-password'): Promise<void> {
  await page.goto('/login?redirect=/task-templates')
  const loginForm = page.getByTestId('login-form')
  if (!(await loginForm.isVisible({ timeout: 3_000 }).catch(() => false))) {
    await page.getByText('退出登录', { exact: true }).first().click({ timeout: 15_000 })
    await expect(loginForm).toBeVisible({ timeout: 30_000 })
  }
  await page.getByTestId('login-email').locator('input').fill(email)
  await page.getByTestId('login-password').locator('input').fill(password)
  await page.getByTestId('login-submit').click()
  await page.waitForURL(/\/(overview|task-templates|task-center)/, { timeout: 60_000 })
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await loginAs(page, adminUser.email)
}
