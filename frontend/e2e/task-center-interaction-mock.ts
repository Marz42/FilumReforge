import type { Page, Route } from '@playwright/test'

import {
  defaultTaskCenterPagination,
  fulfillJson,
  getApiPath,
  getApiPathname,
  isExactApiPath,
  parseQueryParam,
} from './mock-api-helpers'

export const delegateUser = {
  id: 'user-delegate',
  email: 'delegate@example.com',
  role: 'member',
  status: 'active',
  last_login_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

export const TASK_HANDSHAKE_ACCEPT = 'task-handshake-accept'
export const TASK_HANDSHAKE_REJECT = 'task-handshake-reject'
export const TASK_HANDSHAKE_DELEGATE = 'task-handshake-delegate'
export const TASK_BATCH_ROOT = 'task-batch-root-1'
export const GRAPH_HANDSHAKE = 'graph-instance-handshake'
export const GRAPH_BATCH_ROOT = 'graph-batch-root-1'
export const GRAPH_REVIEW = 'graph-instance-1'
export const SCHEDULABLE_GRAPH_TEMPLATE_ID = 'graph-template-schedulable-1'

const schedulableGraphTemplateSummary = {
  id: SCHEDULABLE_GRAPH_TEMPLATE_ID,
  code: 'weekly_capture_v1',
  name: '每周采集',
  status: 'active',
  version: 1,
  run_kind: 'batch',
  config: {
    run_kind: 'batch',
    schedulable: true,
    launch_schema: {
      fields: [{ key: 'theme', label: '主题', type: 'text' }],
    },
    participant_policies: { copywriters: { type: 'department_members' } },
  },
}

type AdminUser = {
  id: string
  email: string
}

type MockTask = {
  id: string
  title: string
  description: string | null
  creator_id: string
  assignee_id: string
  department_id: string
  status: string
  priority: string
  due_date: string | null
  started_at: string | null
  completed_at: string | null
  parent_task_id: string | null
  source_type: string
  extra_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

type GraphInstance = {
  id: string
  workflow_definition_id: string
  status: string
  initiator_user_id?: string
  context?: Record<string, unknown>
  node_instances: Array<{
    id: string
    title: string
    node_key?: string
    iteration: number
    engine_state: string
    activated_at: string | null
    completed_at: string | null
    terminated_at: string | null
    assignee_user_id?: string
  }>
}

export type TaskCenterInteractionMockState = {
  taskPatches: Map<string, Partial<MockTask>>
  graphContexts: Map<string, Record<string, unknown>>
}

export function createTaskCenterInteractionMockState(): TaskCenterInteractionMockState {
  return {
    taskPatches: new Map(),
    graphContexts: new Map(),
  }
}

function buildHandshakeTask(
  adminUser: AdminUser,
  id: string,
  title: string,
  handshakeState: 'assigned' | 'accepted' | 'rejected',
): MockTask {
  return {
    id,
    title,
    description: '图节点握手 E2E',
    creator_id: adminUser.id,
    assignee_id: adminUser.id,
    department_id: 'dept-content',
    status: 'todo',
    priority: 'medium',
    due_date: '2025-04-08T09:00:00Z',
    started_at: null,
    completed_at: null,
    parent_task_id: null,
    source_type: 'manual',
    extra_metadata: {
      workflow_graph_instance_id: GRAPH_HANDSHAKE,
      workflow_node_instance_id: 'graph-node-handshake',
      workflow_handshake_state: handshakeState,
    },
    created_at: '2025-04-04T08:00:00Z',
    updated_at: '2025-04-04T08:00:00Z',
  }
}

export function buildInteractionTasks(adminUser: AdminUser): MockTask[] {
  return [
    buildHandshakeTask(adminUser, TASK_HANDSHAKE_ACCEPT, '握手任务 · 接受', 'assigned'),
    buildHandshakeTask(adminUser, TASK_HANDSHAKE_REJECT, '握手任务 · 协商', 'assigned'),
    buildHandshakeTask(adminUser, TASK_HANDSHAKE_DELEGATE, '握手任务 · 转办', 'assigned'),
    {
      id: TASK_BATCH_ROOT,
      title: '批次 Run · 结束采集',
      description: null,
      creator_id: adminUser.id,
      assignee_id: adminUser.id,
      department_id: 'dept-content',
      status: 'doing',
      priority: 'high',
      due_date: '2025-04-10T09:00:00Z',
      started_at: '2025-04-04T08:00:00Z',
      completed_at: null,
      parent_task_id: null,
      source_type: 'template',
      extra_metadata: {
        workflow_graph_instance_id: GRAPH_BATCH_ROOT,
        workflow_graph_root_task: true,
        run_kind: 'batch',
        template_node_key: 'ROOT_BATCH',
      },
      created_at: '2025-04-04T08:00:00Z',
      updated_at: '2025-04-04T08:00:00Z',
    },
  ]
}

export function buildInteractionInboxItems(adminUser: AdminUser) {
  return [
    {
      task_id: TASK_HANDSHAKE_ACCEPT,
      title: '握手任务 · 接受',
      priority: 'medium',
      status: 'todo',
      due_date: '2025-04-08T09:00:00Z',
      department_name: '内容部',
      current_stage_label: '待确认',
      current_handler_label: '系统管理员',
      user_facing_state: 'pending',
    },
    {
      task_id: TASK_HANDSHAKE_REJECT,
      title: '握手任务 · 协商',
      priority: 'medium',
      status: 'todo',
      due_date: '2025-04-08T09:00:00Z',
      department_name: '内容部',
      current_stage_label: '待确认',
      current_handler_label: '系统管理员',
      user_facing_state: 'pending',
    },
    {
      task_id: TASK_HANDSHAKE_DELEGATE,
      title: '握手任务 · 转办',
      priority: 'medium',
      status: 'todo',
      due_date: '2025-04-08T09:00:00Z',
      department_name: '内容部',
      current_stage_label: '待确认',
      current_handler_label: '系统管理员',
      user_facing_state: 'pending',
    },
  ]
}

export function buildInteractionTrackingItems() {
  return [
    {
      task_id: TASK_BATCH_ROOT,
      title: '批次 Run · 结束采集',
      priority: 'high',
      status: 'doing',
      due_date: '2025-04-10T09:00:00Z',
      department_name: '内容部',
      relation_types: ['发布人'],
      current_stage_label: '采集中',
      current_handler_label: '系统管理员',
      latest_deliverable_submitted_at: null,
      rework_count: 0,
      review_quality_score: null,
      is_pending_review: false,
      user_facing_state: 'in_progress',
      run_label: 'E2E 批次 Run',
    },
  ]
}

export function buildGraphInstances(adminUser: AdminUser): Record<string, GraphInstance> {
  return {
    [GRAPH_REVIEW]: {
      id: GRAPH_REVIEW,
      workflow_definition_id: 'workflow-def-1',
      status: 'in_progress',
      node_instances: [
        {
          id: 'graph-node-start',
          title: '需求澄清',
          iteration: 1,
          engine_state: 'completed',
          activated_at: '2025-04-04T08:00:00Z',
          completed_at: '2025-04-04T08:20:00Z',
          terminated_at: null,
        },
        {
          id: 'graph-node-review',
          title: '验收确认',
          iteration: 1,
          engine_state: 'activated',
          activated_at: '2025-04-04T12:00:00Z',
          completed_at: null,
          terminated_at: null,
        },
      ],
    },
    [GRAPH_HANDSHAKE]: {
      id: GRAPH_HANDSHAKE,
      workflow_definition_id: 'workflow-def-handshake',
      status: 'in_progress',
      node_instances: [
        {
          id: 'graph-node-handshake',
          title: '执行节点',
          iteration: 1,
          engine_state: 'activated',
          activated_at: '2025-04-04T08:00:00Z',
          completed_at: null,
          terminated_at: null,
        },
      ],
    },
    [GRAPH_BATCH_ROOT]: {
      id: GRAPH_BATCH_ROOT,
      workflow_definition_id: 'workflow-def-batch',
      status: 'in_progress',
      initiator_user_id: adminUser.id,
      context: {
        aggregate_mode: 'batch',
        capture_closed: false,
        manager_user_id: adminUser.id,
      },
      node_instances: [
        {
          id: 'graph-node-n2',
          title: '汇总派发',
          node_key: 'N2_AGGREGATE',
          iteration: 1,
          engine_state: 'pending',
          activated_at: null,
          completed_at: null,
          terminated_at: null,
          assignee_user_id: adminUser.id,
        },
      ],
    },
  }
}

export const departmentRunsMock = [
  {
    instance_id: GRAPH_BATCH_ROOT,
    run_label: 'E2E 批次 Run',
    status: 'in_progress',
    event_count: 2,
    created_at: '2025-04-04T08:00:00Z',
  },
]

export const runEventsMock = [
  {
    id: 'event-1',
    instance_id: GRAPH_BATCH_ROOT,
    event_type: 'run_instantiated',
    payload: { reason: '批次实例化' },
    created_at: '2025-04-04T08:00:00Z',
  },
  {
    id: 'event-2',
    instance_id: GRAPH_BATCH_ROOT,
    event_type: 'capture_submitted',
    payload: { reason: '选题已提交' },
    created_at: '2025-04-04T09:00:00Z',
  },
]

function resolveTask(task: MockTask, state: TaskCenterInteractionMockState): MockTask {
  const patch = state.taskPatches.get(task.id)
  if (!patch) {
    return task
  }
  return {
    ...task,
    ...patch,
    extra_metadata: {
      ...task.extra_metadata,
      ...(patch.extra_metadata ?? {}),
    },
  }
}

function resolveGraphInstance(
  instance: GraphInstance,
  state: TaskCenterInteractionMockState,
): GraphInstance {
  const contextPatch = state.graphContexts.get(instance.id)
  if (!contextPatch) {
    return instance
  }
  return {
    ...instance,
    context: {
      ...(instance.context ?? {}),
      ...contextPatch,
    },
  }
}

export function mergeTasksWithInteractions(
  baseTasks: MockTask[],
  interactionTasks: MockTask[],
  state: TaskCenterInteractionMockState,
): MockTask[] {
  const byId = new Map<string, MockTask>()
  for (const task of [...baseTasks, ...interactionTasks]) {
    byId.set(task.id, resolveTask(task, state))
  }
  return [...byId.values()]
}

export async function handleTaskCenterInteractionRoute(
  route: Route,
  options: {
    adminUser: AdminUser
    state: TaskCenterInteractionMockState
    graphInstances: Record<string, GraphInstance>
    allTasks: MockTask[]
  },
): Promise<boolean> {
  const request = route.request()
  const apiPath = getApiPath(request.url())
  const pathname = getApiPathname(apiPath)
  const { adminUser, state, graphInstances, allTasks } = options

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/workflow-graph/runs')) {
    const departmentId = parseQueryParam(apiPath, 'department_id')
    const runs =
      departmentId === 'dept-content' || !departmentId ? departmentRunsMock : []
    await fulfillJson(route, runs)
    return true
  }

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/workflow-graph/templates')) {
    if (parseQueryParam(apiPath, 'schedulable') === 'true') {
      await fulfillJson(route, [schedulableGraphTemplateSummary])
      return true
    }
    return false
  }

  if (
    request.method() === 'POST'
    && /^\/workflow-graph\/templates\/[^/]+\/preview-participants$/.test(pathname)
  ) {
    await fulfillJson(route, {
      policy_ref: 'copywriters',
      mode: 'all',
      user_ids: [adminUser.id, delegateUser.id],
      users: [
        { id: adminUser.id, email: adminUser.email, display_name: '系统管理员' },
        { id: delegateUser.id, email: delegateUser.email, display_name: '协作同事' },
      ],
      snapshot: { mode: 'all', user_ids: [adminUser.id, delegateUser.id] },
    })
    return true
  }

  if (request.method() === 'POST' && isExactApiPath(apiPath, '/workflow-graph/schedules')) {
    const body = request.postDataJSON() as {
      template_id?: string
      name?: string
      scope_department_id?: string
      scope_mode?: string
      cron_expr?: string
      timezone?: string
      participant_mode?: string
    }
    const now = '2025-04-04T08:00:00Z'
    await fulfillJson(
      route,
      {
        id: 'schedule-e2e-1',
        template_id: body.template_id ?? SCHEDULABLE_GRAPH_TEMPLATE_ID,
        template_code: schedulableGraphTemplateSummary.code,
        template_name: schedulableGraphTemplateSummary.name,
        name: body.name?.trim() || 'E2E 周期任务',
        scope_department_id: body.scope_department_id ?? 'dept-content',
        scope_department_name: '内容部',
        scope_mode: body.scope_mode ?? 'self',
        cron_expr: body.cron_expr ?? '0 9 * * 1',
        timezone: body.timezone ?? 'Asia/Shanghai',
        default_inputs: {},
        participant_mode: body.participant_mode ?? 'all',
        participant_user_ids: [],
        exclude_department_ids: [],
        exclude_user_ids: [],
        is_active: true,
        created_by: adminUser.id,
        next_run_at: '2025-04-07T01:00:00Z',
        last_run_at: null,
        last_run_status: null,
        last_run_message: null,
        last_run_instance_count: null,
        created_at: now,
        updated_at: now,
      },
      201,
    )
    return true
  }

  if (request.method() === 'POST' && /^\/workflow-graph\/schedules\/[^/]+\/run-now$/.test(pathname)) {
    await fulfillJson(route, {
      created_count: 1,
      skipped_count: 0,
      failed_count: 0,
      details: [{ department_id: 'dept-content', status: 'created' }],
    })
    return true
  }

  if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+$/.test(pathname)) {
    const instanceId = pathname.slice('/workflow-graph/instances/'.length)
    const base = graphInstances[instanceId]
    if (base) {
      await fulfillJson(route, resolveGraphInstance(base, state))
      return true
    }
    return false
  }

  if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+\/events/.test(pathname)) {
    await fulfillJson(route, { items: runEventsMock, total: runEventsMock.length, limit: 100, offset: 0 })
    return true
  }

  if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+\/submissions/.test(pathname)) {
    const instanceId = pathname.match(/^\/workflow-graph\/instances\/([^/]+)\/submissions/)?.[1]
    const nodeKey = parseQueryParam(apiPath, 'node_key') ?? 'N1_PROPOSE'
    await fulfillJson(route, {
      instance_id: instanceId,
      node_key: nodeKey,
      submissions: [],
    })
    return true
  }

  if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+\/children/.test(pathname)) {
    await fulfillJson(route, [])
    return true
  }

  if (request.method() === 'POST' && /^\/workflow-graph\/instances\/[^/]+\/close-capture$/.test(pathname)) {
    const instanceId = pathname.match(/^\/workflow-graph\/instances\/([^/]+)\/close-capture$/)?.[1]
    if (!instanceId) {
      await fulfillJson(route, { detail: 'Invalid instance id' }, 400)
      return true
    }
    const existing = state.graphContexts.get(instanceId) ?? {}
    state.graphContexts.set(instanceId, { ...existing, capture_closed: true, capture_closed_at: new Date().toISOString() })
    await fulfillJson(route, {
      instance_id: instanceId,
      capture_closed: true,
      capture_closed_at: new Date().toISOString(),
      skipped_capture_count: 0,
      message: '采集已结束，关闭 0 个未提交入口。',
    })
    return true
  }

  const taskActionMatch = pathname.match(/^\/tasks\/([^/]+)\/(accept|reject|delegate|deliverable|review|status)$/)
  if (taskActionMatch && request.method() === 'POST') {
    const [, taskId, action] = taskActionMatch
    const task = allTasks.find((item) => item.id === taskId)
    if (!task) {
      await fulfillJson(route, { detail: 'Task not found' }, 404)
      return true
    }

    const metadata = { ...task.extra_metadata }
    let nextStatus = task.status
    let nextAssignee = task.assignee_id

    if (action === 'accept') {
      metadata.workflow_handshake_state = 'accepted'
    } else if (action === 'reject') {
      metadata.workflow_handshake_state = 'rejected'
      const body = request.postDataJSON() as { reason?: string | null }
      metadata.latest_negotiation_reason = body.reason ?? null
    } else if (action === 'delegate') {
      const body = request.postDataJSON() as { assignee_id?: string; reason?: string | null }
      nextAssignee = body.assignee_id ?? task.assignee_id
      metadata.workflow_handshake_state = 'assigned'
      metadata.latest_delegate_reason = body.reason ?? null
    } else if (action === 'deliverable') {
      nextStatus = 'review'
      metadata.latest_deliverable_summary = 'E2E 交付摘要'
    } else if (action === 'review') {
      const body = request.postDataJSON() as { action?: string }
      nextStatus = body.action === 'approve' ? 'done' : 'doing'
    } else if (action === 'status') {
      const body = request.postDataJSON() as { status?: string }
      nextStatus = body.status ?? task.status
    }

    const updated: Partial<MockTask> = {
      status: nextStatus,
      assignee_id: nextAssignee,
      extra_metadata: metadata,
      updated_at: new Date().toISOString(),
    }
    if (nextStatus === 'done') {
      updated.completed_at = new Date().toISOString()
    }
    state.taskPatches.set(taskId, {
      ...(state.taskPatches.get(taskId) ?? {}),
      ...updated,
    })

    const resolved = resolveTask(task, state)
    await fulfillJson(route, resolved)
    return true
  }

  if (request.method() === 'PATCH' && /^\/tasks\/[^/]+\/status$/.test(pathname)) {
    const taskId = pathname.slice('/tasks/'.length, -'/status'.length)
    const task = allTasks.find((item) => item.id === taskId)
    if (!task) {
      await fulfillJson(route, { detail: 'Task not found' }, 404)
      return true
    }
    const body = request.postDataJSON() as { status?: string }
    state.taskPatches.set(taskId, {
      ...(state.taskPatches.get(taskId) ?? {}),
      status: body.status ?? task.status,
    })
    await fulfillJson(route, resolveTask(task, state))
    return true
  }

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/tasks/stats/scopes')) {
    await fulfillJson(route, {
      mode: 'organization',
      departments: extendPublishDepartmentOptions(),
    })
    return true
  }

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/tasks/stats/summary')) {
    const departmentId = parseQueryParam(apiPath, 'department_id')
    const isPost = departmentId === 'dept-post'
    await fulfillJson(route, {
      total_tasks: isPost ? 8 : 4,
      completed_tasks: isPost ? 5 : 2,
      completion_rate: isPost ? 0.625 : 0.5,
      overdue_tasks: isPost ? 0 : 1,
      overdue_rate: isPost ? 0 : 0.25,
      tasks_by_status: {
        todo: isPost ? 1 : 1,
        doing: isPost ? 2 : 1,
        review: isPost ? 0 : 1,
        done: isPost ? 5 : 1,
      },
      start_date: '2026-07-01',
      end_date: '2026-07-31',
      created_tasks: isPost ? 8 : 4,
      period_completed_tasks: isPost ? 5 : 2,
      due_tasks: isPost ? 6 : 3,
      matured_due_tasks: isPost ? 5 : 2,
      on_time_completed_tasks: isPost ? 5 : 1,
      on_time_completion_rate: isPost ? 1 : 0.5,
      current_open_tasks: isPost ? 3 : 2,
      period_overdue_tasks: isPost ? 0 : 1,
    })
    return true
  }

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/tasks/stats/workload')) {
    const departmentId = parseQueryParam(apiPath, 'department_id')
    await fulfillJson(route, [
      {
        assignee_id: adminUser.id,
        assignee_email: adminUser.email,
        assignee_label: departmentId === 'dept-post' ? '后期负责人' : '系统管理员',
        department_id: departmentId ?? 'dept-content',
        department_name: departmentId === 'dept-post' ? '后期部' : '内容部',
        total_tasks: departmentId === 'dept-post' ? 8 : 4,
        open_tasks: departmentId === 'dept-post' ? 3 : 2,
        completed_tasks: departmentId === 'dept-post' ? 5 : 2,
        overdue_tasks: departmentId === 'dept-post' ? 0 : 1,
        created_tasks: departmentId === 'dept-post' ? 8 : 4,
        period_completed_tasks: departmentId === 'dept-post' ? 5 : 2,
        due_tasks: departmentId === 'dept-post' ? 6 : 3,
        matured_due_tasks: departmentId === 'dept-post' ? 5 : 2,
        on_time_completed_tasks: departmentId === 'dept-post' ? 5 : 1,
        on_time_completion_rate: departmentId === 'dept-post' ? 1 : 0.5,
        period_overdue_tasks: departmentId === 'dept-post' ? 0 : 1,
      },
    ])
    return true
  }

  if (request.method() === 'GET' && isExactApiPath(apiPath, '/tasks/stats/details')) {
    await fulfillJson(route, { items: [], next_cursor: null, has_more: false })
    return true
  }

  return false
}

export async function installTaskCenterInteractionMock(page: Page): Promise<TaskCenterInteractionMockState> {
  const state = createTaskCenterInteractionMockState()
  await page.addInitScript(() => {
    window.localStorage.setItem('filum.access_token', 'playwright-access-token')
  })
  return state
}

export function extendPublishDepartmentOptions() {
  return [
    { id: 'dept-content', label: '内容部' },
    { id: 'dept-post', label: '后期部' },
  ]
}

export function extendPublishUserOptions(adminUser: AdminUser) {
  return [
    {
      user_id: adminUser.id,
      email: adminUser.email,
      real_name: '系统管理员',
      department_id: 'dept-content',
      department_name: '内容部',
      label: '系统管理员（admin@example.com）',
    },
    {
      user_id: delegateUser.id,
      email: delegateUser.email,
      real_name: '协作同事',
      department_id: 'dept-content',
      department_name: '内容部',
      label: '协作同事（delegate@example.com）',
    },
  ]
}

export { defaultTaskCenterPagination }
