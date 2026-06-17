import { expect, type Page, type Route } from '@playwright/test'

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

export const VIDEO_DEMO_ACCOUNTS = {
  copyLead: copyLeadUser.email,
  copyA: 'demo.video.copy.a@example.com',
  copyB: 'demo.video.copy.b@example.com',
  copyC: 'demo.video.copy.c@example.com',
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

const allDemoUsers = [copyLeadUser, ...editorUsers, adminUser]

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
  finalized: false,
  forked: false,
  /** When false, `/auth/refresh` returns 401 so the login form is shown (guestOnly redirect). */
  sessionActive: false,
  rejectedTopicIds: new Set<string>(),
  currentUserId: copyLeadUser.id,
  runLabel: 'E2E多账号批次',
  productionTasks: [] as Array<{
    scriptTaskId: string
    reviewTaskId: string
    authorId: string
    deliverableDone: boolean
    reviewDone: boolean
  }>,
}

export function resetVideoMockForMultiAccount(runLabel: string): void {
  videoMockState.captureSubmitted.clear()
  videoMockState.rejectedTopicIds.clear()
  videoMockState.finalized = false
  videoMockState.forked = false
  videoMockState.childInstanceIds = []
  videoMockState.childRootTaskIds = []
  videoMockState.productionTasks = []
  videoMockState.runLabel = runLabel
  videoMockState.sessionActive = false
  videoMockState.currentUserId = copyLeadUser.id
}

function buildCaptureTask(editorId: string, taskId: string) {
  const editor = editorUsers.find((user) => user.id === editorId) ?? editorUsers[0]
  return {
    id: taskId,
    title: '选题会（批次） / 提交选题',
    description: null,
    creator_id: adminUser.id,
    // E2E 以管理员登录，采集面板仅对当前 assignee 可见
    assignee_id: editor.id,
    department_id: 'dept-video-copy',
    status: videoMockState.captureSubmitted.has(taskId) ? 'review' : 'doing',
    priority: 'medium',
    due_date: null,
    started_at: '2025-05-01T08:00:00Z',
    completed_at: null,
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
    },
    created_at: '2025-05-01T08:00:00Z',
    updated_at: '2025-05-01T08:00:00Z',
  }
}

const captureTasks = [
  buildCaptureTask('user-editor-a', 'task-capture-a'),
  buildCaptureTask('user-editor-b', 'task-capture-b'),
  buildCaptureTask('user-editor-c', 'task-capture-c'),
]

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

function buildProductionScriptTask(scriptTaskId: string, authorId: string, topicLabel: string) {
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
      workflow_graph_instance_id: 'child-inst-1',
      workflow_node_instance_id: `ni-script-${scriptTaskId}`,
      template_node_key: 'N3_SCRIPT_WRITE',
      run_kind: 'production',
    },
    created_at: '2025-05-01T11:00:00Z',
    updated_at: '2025-05-01T11:00:00Z',
  }
}

function buildProductionReviewTask(reviewTaskId: string, topicLabel: string) {
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
      workflow_graph_instance_id: 'child-inst-1',
      workflow_node_instance_id: `ni-review-${reviewTaskId}`,
      template_node_key: 'N4_SCRIPT_REVIEW',
      run_kind: 'production',
    },
    created_at: '2025-05-01T12:00:00Z',
    updated_at: '2025-05-01T12:00:00Z',
  }
}

function buildTaskCenterSnapshot() {
  const root = buildRootTask()
  const aggregate = buildAggregateTask()
  const currentUserId = videoMockState.currentUserId
  const tracking = [
    toTaskCenterTrackingItem(root, '批次运行'),
    toTaskCenterTrackingItem(aggregate, '汇总派发'),
    ...captureTasks.map((task) => toTaskCenterTrackingItem(task, '提交选题')),
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

  const inboxTasks: VideoMockTask[] = captureTasks.filter(
    (task) => !videoMockState.captureSubmitted.has(task.id) && task.assignee_id === currentUserId,
  )
  for (const production of videoMockState.productionTasks) {
    if (!production.deliverableDone && production.authorId === currentUserId) {
      inboxTasks.push(
        buildProductionScriptTask(
          production.scriptTaskId,
          production.authorId,
          production.scriptTaskId,
        ),
      )
    }
    if (!production.reviewDone && copyLeadUser.id === currentUserId) {
      inboxTasks.push(buildProductionReviewTask(production.reviewTaskId, production.reviewTaskId))
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
      run_label: videoMockState.runLabel,
      inputs: { theme: 'W10 E2E', manager_user_id: copyLeadUser.id },
      root_task_id: rootTaskId,
      fork_status: videoMockState.forked ? 'completed' : 'pending',
      forked_child_instance_ids: videoMockState.childInstanceIds,
      schema_snapshot: {
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
  return {
    id: childId,
    template_id: productionTemplateId,
    initiator_user_id: adminUser.id,
    department_id: 'dept-video-copy',
    source_type: 'template',
    status: 'active',
    current_node_key: 'N3_SCRIPT_WRITE',
    run_label: topicTitle,
    parent_instance_id: batchInstanceId,
    context: {
      run_kind: 'production',
      topic_title: topicTitle,
      root_task_id: rootTask,
      script_author_id: adminUser.id,
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
        },
      },
    },
    context_version: 1,
    max_iterations: 5,
    completed_at: null,
    created_at: '2025-05-01T11:00:00Z',
    node_instances: [
      {
        id: `ni-script-${childId}`,
        instance_id: childId,
        template_node_id: 'tn-n3',
        node_key: 'N3_SCRIPT_WRITE',
        title: '撰写脚本',
        node_type: 'task',
        engine_state: 'activated',
        business_state: 'doing',
        assignee_user_id: adminUser.id,
        iteration: 1,
        activated_at: '2025-05-01T11:00:00Z',
        completed_at: null,
        terminated_at: null,
        created_at: '2025-05-01T11:00:00Z',
      },
    ],
    total_node_count: 1,
    completed_node_count: 0,
    active_node_count: 1,
    pending_node_count: 0,
    progress_percent: 0,
  }
}

async function fulfillJson(route: Route, data: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  })
}

function getApiPath(url: string): string {
  const parsed = new URL(url)
  const apiPrefix = '/api/v1'
  const prefixIndex = parsed.pathname.indexOf(apiPrefix)
  const path = prefixIndex >= 0 ? parsed.pathname.slice(prefixIndex + apiPrefix.length) : parsed.pathname
  return path
}

export async function installWorkflowVideoMockApi(page: Page): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const apiPath = getApiPath(request.url())

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

    if (request.method() === 'GET' && apiPath === '/workflow-graph/templates') {
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
      const submissions = captureTasks
        .filter((task) => videoMockState.captureSubmitted.has(task.id))
        .map((task) => {
          const topicIndex = captureTasks.findIndex((capture) => capture.id === task.id)
          return {
          node_instance_id: task.extra_metadata.workflow_node_instance_id,
          node_key: 'N1_PROPOSE',
          instance_key: task.extra_metadata.template_node_instance_key,
          assignee_user_id: task.assignee_id,
          assignee_email: editorUsers[topicIndex]?.email ?? adminUser.email,
          topics: [
            {
              topic_id: videoMockState.topicIds[topicIndex],
              title: `选题 ${String.fromCharCode(65 + topicIndex)}`,
              content: null,
              reason: null,
            },
          ],
        }
        })
      await fulfillJson(route, { instance_id: batchInstanceId, node_key: 'N1_PROPOSE', submissions })
      return
    }

    if (request.method() === 'POST' && apiPath === `/workflow-graph/instances/${batchInstanceId}/reject-captures`) {
      const body = request.postDataJSON() as { topic_ids?: string[]; reason?: string }
      for (const topicId of body.topic_ids ?? []) {
        videoMockState.rejectedTopicIds.add(topicId)
      }
      await fulfillJson(route, {
        instance_id: batchInstanceId,
        rejected_count: body.topic_ids?.length ?? 0,
        reason: body.reason ?? 'UAT mock reject',
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
        const scriptTaskId = `task-n3-${index + 1}`
        const reviewTaskId = `task-n4-${index + 1}`
        const authorId = editorUsers[index]?.id ?? editorUsers[0].id
        videoMockState.childInstanceIds.push(childId)
        videoMockState.childRootTaskIds.push(childTaskId)
        videoMockState.productionTasks.push({
          scriptTaskId,
          reviewTaskId,
          authorId,
          deliverableDone: false,
          reviewDone: false,
        })
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
      const children = videoMockState.childInstanceIds.map((childId, index) =>
        buildChildGraphInstance(childId, `选题 ${String.fromCharCode(65 + index)}`, videoMockState.childRootTaskIds[index] ?? ''),
      )
      await fulfillJson(route, children)
      return
    }

    if (request.method() === 'GET' && apiPath === `/workflow-graph/instances/${batchInstanceId}/events`) {
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

    if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+$/.test(apiPath)) {
      const instanceId = apiPath.split('/')[2]
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

    if (request.method() === 'POST' && /^\/workflow-graph\/tasks\/[^/]+\/submit-capture$/.test(apiPath)) {
      const taskId = apiPath.split('/').filter(Boolean)[2] ?? ''
      videoMockState.captureSubmitted.add(taskId)
      const topicIndex = captureTasks.findIndex((task) => task.id === taskId)
      await fulfillJson(route, {
        task_id: taskId,
        node_instance_id: `ni-capture-${captureTasks[topicIndex]?.assignee_id ?? 'a'}`,
        topic_count: 1,
        topics: [{ topic_id: videoMockState.topicIds[topicIndex], title: `选题 ${String.fromCharCode(65 + topicIndex)}` }],
      })
      return
    }

    if (request.method() === 'GET' && apiPath === '/task-center') {
      await fulfillJson(route, buildTaskCenterSnapshot())
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks') {
      const allTasks = [buildRootTask(), buildAggregateTask(), ...captureTasks]
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
      await fulfillJson(route, allTasks)
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/views/board') {
      await fulfillJson(route, [
        { status: 'todo', tasks: [] },
        { status: 'doing', tasks: captureTasks },
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

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/activity$/.test(apiPath)) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/watchers$/.test(apiPath)) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/attachments')) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'POST' && /^\/tasks\/[^/]+\/deliverable$/.test(apiPath)) {
      const taskId = apiPath.split('/').filter(Boolean)[1] ?? ''
      const production = videoMockState.productionTasks.find((item) => item.scriptTaskId === taskId)
      if (production) {
        production.deliverableDone = true
      }
      await fulfillJson(route, { id: taskId, status: 'review' })
      return
    }

    if (
      request.method() === 'POST'
      && (/^\/tasks\/[^/]+\/review$/.test(apiPath) || /^\/tasks\/[^/]+\/deliverable\/review$/.test(apiPath))
    ) {
      const taskId = apiPath.split('/').filter(Boolean)[1] ?? ''
      const production = videoMockState.productionTasks.find((item) => item.reviewTaskId === taskId)
      if (production) {
        production.reviewDone = true
      }
      await fulfillJson(route, { id: taskId, status: 'done' })
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+$/.test(apiPath)) {
      const segments = apiPath.split('/').filter(Boolean)
      const taskId = segments[1]
      let task = [buildRootTask(), buildAggregateTask(), ...captureTasks].find((item) => item.id === taskId)
      const production = videoMockState.productionTasks.find(
        (item) => item.scriptTaskId === taskId || item.reviewTaskId === taskId,
      )
      if (!task && production) {
        if (production.scriptTaskId === taskId) {
          task = buildProductionScriptTask(production.scriptTaskId, production.authorId, `题${production.scriptTaskId}`)
        } else {
          task = buildProductionReviewTask(production.reviewTaskId, `题${production.reviewTaskId}`)
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
