import { expect, test as base, type Page, type Route } from '@playwright/test'

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

const allMockTasks = [mockInboxTask, selectedTask, mockHistoryTask]

const taskCenterSnapshot = {
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
  publish_department_options: [
    {
      id: 'dept-content',
      label: '内容部',
    },
  ],
  publish_user_options: [
    {
      user_id: adminUser.id,
      email: adminUser.email,
      real_name: '系统管理员',
      department_id: 'dept-content',
      department_name: '内容部',
      label: '系统管理员（admin@example.com）',
    },
  ],
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
    },
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
    },
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
    },
  ],
  task_memos: [],
}

const taskStatsSummary = {
  total_tasks: 4,
  completed_tasks: 2,
  completion_rate: 0.5,
  overdue_tasks: 1,
  overdue_rate: 0.25,
  tasks_by_status: {
    todo: 1,
    doing: 1,
    review: 1,
    done: 1,
  },
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

const graphInstance = {
  id: 'graph-instance-1',
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
}

async function fulfillJson(route: Route, data: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  })
}

async function fulfillUnauthorized(route: Route): Promise<void> {
  await fulfillJson(route, { detail: 'unauthorized' }, 401)
}

function getApiPath(url: string): string {
  const parsed = new URL(url)
  const apiPrefix = '/api/v1'
  const prefixIndex = parsed.pathname.indexOf(apiPrefix)
  const path = prefixIndex >= 0 ? parsed.pathname.slice(prefixIndex + apiPrefix.length) : parsed.pathname
  return `${path}${parsed.search}`
}

async function installMockApi(page: Page, options: MockApiOptions = {}): Promise<void> {
  const authenticated = options.authenticated ?? true

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const apiPath = getApiPath(request.url())

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
      await fulfillJson(route, taskCenterSnapshot)
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks') {
      await fulfillJson(route, allMockTasks)
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+$/.test(apiPath)) {
      const taskId = apiPath.slice('/tasks/'.length)
      const task = allMockTasks.find((item) => item.id === taskId)
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
      await fulfillJson(route, [adminUser])
      return
    }

    if (request.method() === 'GET' && apiPath.startsWith('/messages')) {
      await fulfillJson(route, messageCenterSnapshot)
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/stats/summary') {
      await fulfillJson(route, taskStatsSummary)
      return
    }

    if (request.method() === 'GET' && apiPath === '/tasks/stats/workload') {
      await fulfillJson(route, [
        {
          assignee_id: adminUser.id,
          assignee_email: adminUser.email,
          department_id: 'dept-content',
          department_name: '内容部',
          total_tasks: 4,
          open_tasks: 2,
          completed_tasks: 2,
          overdue_tasks: 1,
        },
      ])
      return
    }

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/activity$/.test(apiPath)) {
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

    if (request.method() === 'GET' && /^\/tasks\/[^/]+\/watchers$/.test(apiPath)) {
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

    if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+\/events/.test(apiPath)) {
      await fulfillJson(route, { items: [], total: 0, limit: 50, offset: 0 })
      return
    }

    if (request.method() === 'GET' && /^\/workflow-graph\/instances\/[^/]+$/.test(apiPath)) {
      await fulfillJson(route, graphInstance)
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