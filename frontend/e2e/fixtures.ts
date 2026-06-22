import { expect, test as base, type Page, type Route } from '@playwright/test'

import {
  defaultTaskCenterPagination,
  fulfillJson,
  fulfillTaskCenterListPage,
  fulfillTasksListGet,
  getApiPath,
  getApiPathname,
  isExactApiPath,
  parseQueryParam,
} from './mock-api-helpers'
import {
  buildGraphInstances,
  buildInteractionInboxItems,
  buildInteractionTasks,
  buildInteractionTrackingItems,
  createTaskCenterInteractionMockState,
  delegateUser,
  extendPublishDepartmentOptions,
  extendPublishUserOptions,
  handleTaskCenterInteractionRoute,
  mergeTasksWithInteractions,
  type TaskCenterInteractionMockState,
} from './task-center-interaction-mock'

type MockApiOptions = {
  authenticated?: boolean
}

const adminUser = {
  id: 'user-admin',
  email: 'admin@example.com',
  role: 'admin',
  status: 'active',
  last_login_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

const authSession = {
  access_token: 'playwright-access-token',
  token_type: 'bearer',
  user: adminUser,
}

const selectedTask = {
  id: 'task-graph-1',
  title: '完善工作流看板验收流',
  description: '验证任务中心和图节点板块在浏览器端的真实交互。',
  creator_id: adminUser.id,
  assignee_id: adminUser.id,
  department_id: 'dept-content',
  status: 'review',
  priority: 'high',
  due_date: '2025-04-05T10:00:00Z',
  started_at: '2025-04-04T08:00:00Z',
  completed_at: null,
  parent_task_id: null,
  source_type: 'template',
  extra_metadata: {
    workflow_graph_instance_id: 'graph-instance-1',
    workflow_node_instance_id: 'graph-node-review',
    workflow_handshake_state: 'accepted',
    latest_deliverable_summary: '已提交图追踪和任务详情收口结果。',
    latest_deliverable_submitted_at: '2025-04-04T12:00:00Z',
    latest_review_quality_score: 4,
    rework_count: 1,
  },
  created_at: '2025-04-03T08:00:00Z',
  updated_at: '2025-04-04T12:30:00Z',
}

const mockInboxTask = {
  id: 'task-inbox-1',
  title: '整理四月周报',
  description: null,
  creator_id: adminUser.id,
  assignee_id: adminUser.id,
  department_id: 'dept-content',
  status: 'todo',
  priority: 'high',
  due_date: '2025-04-06T09:00:00Z',
  started_at: null,
  completed_at: null,
  parent_task_id: null,
  source_type: 'manual',
  extra_metadata: {},
  created_at: '2025-04-03T08:00:00Z',
  updated_at: '2025-04-03T08:00:00Z',
}

const mockHistoryTask = {
  id: 'task-history-1',
  title: '归档旧公告',
  description: null,
  creator_id: adminUser.id,
  assignee_id: adminUser.id,
  department_id: 'dept-content',
  status: 'done',
  priority: 'low',
  due_date: '2025-04-01T09:00:00Z',
  started_at: null,
  completed_at: '2025-04-01T10:00:00Z',
  parent_task_id: null,
  source_type: 'manual',
  extra_metadata: {},
  created_at: '2025-04-01T08:00:00Z',
  updated_at: '2025-04-01T10:00:00Z',
}

const baseMockTasks = [mockInboxTask, selectedTask, mockHistoryTask]
const interactionTasks = buildInteractionTasks(adminUser)
const graphInstances = buildGraphInstances(adminUser)
const dynamicCreatedTasks: typeof baseMockTasks = []
let interactionMockState: TaskCenterInteractionMockState = createTaskCenterInteractionMockState()

function getAllMockTasks() {
  return mergeTasksWithInteractions(
    [...baseMockTasks, ...dynamicCreatedTasks],
    interactionTasks,
    interactionMockState,
  )
}

function buildTaskCenterSnapshot() {
  return {
    permissions: {
      can_manage_templates: true,
      can_publish_task: true,
    },
    template_summaries: [
      {
        id: 'template-1',
        name: '内容发布模板',
        category: 'ops',
        is_active: true,
        step_count: 3,
      },
    ],
    publish_department_options: extendPublishDepartmentOptions(),
    publish_user_options: extendPublishUserOptions(adminUser),
    task_inbox: [
      {
        task_id: 'task-inbox-1',
        title: '整理四月周报',
        priority: 'high',
        status: 'todo',
        due_date: '2025-04-06T09:00:00Z',
        department_name: '内容部',
        current_stage_label: '待处理',
        current_handler_label: '系统管理员',
        user_facing_state: 'pending',
      },
      ...buildInteractionInboxItems(adminUser),
      ...dynamicCreatedTasks.map((task) => ({
        task_id: task.id,
        title: task.title,
        priority: task.priority,
        status: task.status,
        due_date: task.due_date,
        department_name: '内容部',
        current_stage_label: '待处理',
        current_handler_label: '系统管理员',
        user_facing_state: 'pending',
      })),
    ],
    task_tracking: [
      {
        task_id: selectedTask.id,
        title: selectedTask.title,
        priority: selectedTask.priority,
        status: selectedTask.status,
        due_date: selectedTask.due_date,
        department_name: '内容部',
        relation_types: ['发布人'],
        current_stage_label: '验收中',
        current_handler_label: '系统管理员',
        latest_deliverable_submitted_at: '2025-04-04T12:00:00Z',
        rework_count: 1,
        review_quality_score: 4,
        is_pending_review: true,
        user_facing_state: 'awaiting_confirm',
        run_label: '验收 Run A',
      },
      ...buildInteractionTrackingItems(),
    ],
    task_history: [
      {
        task_id: 'task-history-1',
        title: '归档旧公告',
        priority: 'low',
        due_date: '2025-04-01T09:00:00Z',
        completed_at: '2025-04-01T10:00:00Z',
        department_name: '内容部',
        relation_types: ['执行'],
        source_type: 'manual',
        user_facing_state: 'completed',
      },
    ],
    task_memos: [],
    inbox_pagination: defaultTaskCenterPagination,
    tracking_pagination: defaultTaskCenterPagination,
    history_pagination: defaultTaskCenterPagination,
  }
}

const messageCenterSnapshot = {
  items: [
    {
      id: 'message-1',
      source_type: 'task',
      source_id: 'task-inbox-1',
      recipient_user_id: adminUser.id,
      recipient_email: adminUser.email,
      message_type: 'task_assigned',
      title: '整理四月周报',
      body_text: '你有一条新的任务待处理。',
      body_html: null,
      payload: {},
      status: 'completed',
      scheduled_at: null,
      enqueued_at: '2025-04-04T08:00:00Z',
      completed_at: '2025-04-04T08:00:00Z',
      created_at: '2025-04-04T08:00:00Z',
      delivery_state: 'sent',
      source: {
        module_key: 'task',
        module_label: '任务中心',
        object_type: 'task',
        object_id: 'task-inbox-1',
        object_label: '整理四月周报',
        target: {
          route_name: 'task-center',
          route_query: { tab: 'tracking', selected: 'task-inbox-1' },
          can_navigate: true,
        },
      },
      receipt_state: {
        is_read: false,
        is_acknowledged: false,
        read_at: null,
        acknowledged_at: null,
      },
      attachments: [],
      deliveries: [],
      receipts: [],
    },
  ],
  total_count: 1,
  filtered_count: 1,
  unread_count: 1,
  unacknowledged_count: 1,
  source_counts: [{ source_type: 'task', label: '任务中心', count: 1 }],
}

async function fulfillUnauthorized(route: Route): Promise<void> {
  await fulfillJson(route, { detail: 'unauthorized' }, 401)
}

async function installMockApi(page: Page, options: MockApiOptions = {}): Promise<void> {
  const authenticated = options.authenticated ?? true
  dynamicCreatedTasks.length = 0
  interactionMockState = createTaskCenterInteractionMockState()

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const apiPath = getApiPath(request.url())
    const pathname = getApiPathname(apiPath)
    const snapshot = buildTaskCenterSnapshot()
    const tasks = getAllMockTasks()

    if (request.method() === 'GET' && apiPath === '/auth/bootstrap-status') {
      await fulfillJson(route, { bootstrap_required: false })
      return
    }

    if (request.method() === 'POST' && apiPath === '/auth/login') {
      await fulfillJson(route, authSession)
      return
    }

    if (request.method() === 'POST' && apiPath === '/auth/refresh') {
      if (authenticated) {
        await fulfillJson(route, authSession)
      } else {
        await fulfillUnauthorized(route)
      }
      return
    }

    if (request.method() === 'GET' && apiPath === '/auth/me') {
      await fulfillJson(route, adminUser)
      return
    }

    if (request.method() === 'GET' && apiPath === '/task-center') {
      await fulfillJson(route, snapshot)
      return
    }

    if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/inbox', snapshot.task_inbox)) {
      return
    }

    if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/tracking', snapshot.task_tracking)) {
      return
    }

    if (await fulfillTaskCenterListPage(route, apiPath, '/task-center/history', snapshot.task_history)) {
      return
    }

    if (request.method() === 'GET' && isExactApiPath(apiPath, '/tasks/search')) {
      const query = parseQueryParam(apiPath, 'q')?.trim().toLowerCase() ?? ''
      const results = tasks
        .filter((task) => task.title.toLowerCase().includes(query))
        .map((task) => ({
          id: task.id,
          title: task.title,
          description: task.description,
          status: task.status,
          priority: task.priority,
          due_date: task.due_date,
          user_facing_state: task.id === selectedTask.id ? 'awaiting_confirm' : 'pending',
        }))
      await fulfillJson(route, results)
      return
    }

    if (request.method() === 'POST' && apiPath === '/tasks') {
      const body = request.postDataJSON() as {
        title?: string
        description?: string | null
        assignee_id?: string
        department_id?: string | null
        priority?: string
        due_date?: string | null
      }
      const createdTask = {
        id: 'task-created-e2e',
        title: body.title?.trim() || '未命名任务',
        description: body.description ?? null,
        creator_id: adminUser.id,
        assignee_id: body.assignee_id ?? adminUser.id,
        department_id: body.department_id ?? 'dept-content',
        status: 'todo',
        priority: body.priority ?? 'medium',
        due_date: body.due_date ?? null,
        started_at: null,
        completed_at: null,
        parent_task_id: null,
        source_type: 'manual',
        extra_metadata: {},
        created_at: '2025-04-04T08:00:00Z',
        updated_at: '2025-04-04T08:00:00Z',
      }
      dynamicCreatedTasks.push(createdTask)
      await fulfillJson(route, createdTask, 201)
      return
    }

    if (await fulfillTasksListGet(route, apiPath, tasks)) {
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/?]+$/.test(pathname)) {
      const taskId = pathname.slice('/tasks/'.length)
      const task = tasks.find((item) => item.id === taskId)
      if (task) {
        await fulfillJson(route, task)
      } else {
        await fulfillJson(route, { detail: 'Task not found' }, 404)
      }
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/views/board') {
      await fulfillJson(route, [
        { status: 'todo', tasks: [] },
        { status: 'doing', tasks: [] },
        { status: 'review', tasks: [selectedTask] },
        { status: 'done', tasks: [] },
      ])
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/views/gantt') {
      await fulfillJson(route, [{ task: selectedTask, dependency_ids: ['task-inbox-1'] }])
      return
    }

    if (request.method() === 'GET' && apiPath === '/departments') {
      await fulfillJson(route, [
        {
          id: 'dept-content',
          name: '内容部',
          code: 'content',
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

    if (request.method() === 'GET' && apiPath === '/users') {
      await fulfillJson(route, [adminUser, delegateUser])
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/messages')) {
      await fulfillJson(route, messageCenterSnapshot)
      return
    }

    if (
      await handleTaskCenterInteractionRoute(route, {
        adminUser,
        state: interactionMockState,
        graphInstances,
        allTasks: tasks,
      })
    ) {
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/activity$/.test(pathname)) {
      await fulfillJson(route, [
        {
          entry_type: 'log',
          created_at: '2025-04-04T08:10:00Z',
          comment: null,
          log: {
            id: 'log-1',
            task_id: selectedTask.id,
            operator_id: adminUser.id,
            action_type: 'created',
            from_status: null,
            to_status: null,
            detail: {},
            created_at: '2025-04-04T08:10:00Z',
          },
        },
      ])
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/watchers$/.test(pathname)) {
      await fulfillJson(route, [])
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/attachments?')) {
      await fulfillJson(route, [
        {
          id: 'att-mock-1',
          original_filename: 'mock-spec.pdf',
          mime_type: 'application/pdf',
          size_bytes: 128,
          checksum_sha256: '0'.repeat(64),
          uploader_id: adminUser.id,
          visibility: 'private',
          status: 'uploaded',
          deleted_at: null,
          created_at: '2025-04-04T08:00:00Z',
          download_url: 'https://example.com/mock.pdf',
        },
      ])
      return
    }

    await fulfillJson(route, { detail: `unhandled mock: ${request.method()} ${apiPath}` }, 404)
  })
}

export const test = base.extend<{ mockApi: (options?: MockApiOptions) => Promise<void> }>({
  mockApi: async ({ page }, use) => {
    await use(async (options?: MockApiOptions) => {
      await installMockApi(page, options)
    })
  },
})

export { expect }

export async function loginFromPage(page: Page): Promise<void> {
  await page.goto('/login?redirect=/task-center')
  await page.locator('[data-testid="login-email"] input').fill(adminUser.email)
  await page.locator('[data-testid="login-password"] input').fill('secret-password')
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/task-center/)
  await expect(page.getByTestId('task-center-view')).toBeVisible()
}