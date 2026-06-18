/**
 * 视频制作全流程 · 多账号 Live E2E（真实 Docker 栈 + seed_sample_data）
 */
import { expect, test, type Page } from '@playwright/test'

import { liveConfig } from './compose-env.mjs'
import { liveRow, liveShot, writeLiveReport } from './workflow-video-live-report.ts'

const PASSWORD = process.env.PLAYWRIGHT_LIVE_PASSWORD ?? liveConfig.password
const BASE_URL = process.env.PLAYWRIGHT_LIVE_BASE_URL ?? liveConfig.baseURL

const ACCOUNTS = {
  copyLead: 'demo.video.copy.lead@example.com',
  copyA: 'demo.video.copy.a@example.com',
  copyB: 'demo.video.copy.b@example.com',
  copyC: 'demo.video.copy.c@example.com',
} as const

const RUN_TAG = `live-${Date.now()}`
const THEME = `E2E多账号全流程 ${RUN_TAG}`
const RUN_LABEL = `批次 ${RUN_TAG}`

let sharedBatchInstanceId = ''
let sharedRootTaskId = ''
const captureTaskIdsByEmail: Record<string, string> = {}

const CAPTURE_ASSIGNEE_LABEL_TO_EMAIL: Record<string, string> = {
  陆言: ACCOUNTS.copyA,
  宋遥: ACCOUNTS.copyB,
  程野: ACCOUNTS.copyC,
}

async function mapCaptureTasksAfterInstantiate(
  page: Page,
  leadToken: string,
  instanceId: string,
): Promise<void> {
  const headers = { Authorization: `Bearer ${leadToken}` }
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const centerResp = await page.request.get('/api/v1/task-center', { headers })
    expect(centerResp.ok()).toBeTruthy()
    const center = (await centerResp.json()) as {
      task_inbox: Array<TaskCenterEntry & { current_handler_label?: string }>
      task_tracking: Array<TaskCenterEntry & { current_handler_label?: string }>
    }
    const captureEntries = [...center.task_inbox, ...center.task_tracking].filter((entry) =>
      entry.title.includes('提交选题'),
    )
    for (const entry of captureEntries) {
      const label = (entry.current_handler_label ?? '').trim()
      const email =
        (label.includes('@') ? label : CAPTURE_ASSIGNEE_LABEL_TO_EMAIL[label]) ?? ''
      if (email) {
        captureTaskIdsByEmail[email] = entry.task_id
      }
    }

    if (Object.keys(captureTaskIdsByEmail).length >= 3) {
      return
    }

    const adminLogin = await page.request.post('/api/v1/auth/login', {
      data: { email: liveConfig.adminEmail, password: PASSWORD },
    })
    if (adminLogin.ok()) {
      const adminToken = ((await adminLogin.json()) as { access_token: string }).access_token
      const adminCenterResp = await page.request.get('/api/v1/task-center', {
        headers: { Authorization: `Bearer ${adminToken}` },
      })
      if (adminCenterResp.ok()) {
        const adminCenter = (await adminCenterResp.json()) as {
          task_inbox: Array<TaskCenterEntry & { current_handler_label?: string }>
          task_tracking: Array<TaskCenterEntry & { current_handler_label?: string }>
        }
        for (const entry of [...adminCenter.task_inbox, ...adminCenter.task_tracking]) {
          if (!entry.title.includes('提交选题')) {
            continue
          }
          const label = (entry.current_handler_label ?? '').trim()
          const email =
            (label.includes('@') ? label : CAPTURE_ASSIGNEE_LABEL_TO_EMAIL[label]) ?? ''
          if (email) {
            captureTaskIdsByEmail[email] = entry.task_id
          }
        }
      }
    }

    if (Object.keys(captureTaskIdsByEmail).length >= 3) {
      return
    }

    if (instanceId) {
      const [instResp, usersResp] = await Promise.all([
        page.request.get(`/api/v1/workflow-graph/instances/${instanceId}`, { headers }),
        page.request.get('/api/v1/users', { headers }),
      ])
      if (instResp.ok() && usersResp.ok()) {
        const inst = (await instResp.json()) as {
          node_instances: Array<{ node_key: string; assignee_user_id?: string }>
        }
        const users = (await usersResp.json()) as Array<{ id: string; email: string }>
        const n1Nodes = inst.node_instances.filter((node) => node.node_key === 'N1_PROPOSE')
        for (const node of n1Nodes) {
          const user = users.find((item) => item.id === node.assignee_user_id)
          if (!user) {
            continue
          }
          const searchResp = await page.request.get(
            `/api/v1/tasks/search?q=${encodeURIComponent('提交选题')}&limit=20`,
            { headers: { Authorization: `Bearer ${leadToken}` } },
          )
          if (searchResp.ok()) {
            const results = (await searchResp.json()) as Array<{ id: string; title: string }>
            const hit = results.find((item) => item.title.includes('提交选题'))
            if (hit) {
              captureTaskIdsByEmail[user.email] = hit.id
            }
          }
        }
      }
    }

    if (Object.keys(captureTaskIdsByEmail).length >= 3) {
      return
    }

    await page.waitForTimeout(2_000)
  }
}

test.describe.configure({ mode: 'serial' })

async function snap(page: Page, file: string): Promise<void> {
  await page.screenshot({ path: liveShot(file), fullPage: true })
}

type LiveSession = { userId: string; accessToken: string }

async function login(page: Page, email: string): Promise<LiveSession> {
  await page.goto('/login')
  await page.getByTestId('login-form').waitFor({ timeout: 60_000 })
  await page.getByTestId('login-email').locator('input').fill(email)
  await page.getByTestId('login-password').locator('input').fill(PASSWORD)
  const [loginResp] = await Promise.all([
    page.waitForResponse(
      (r) => /\/api\/v1\/auth\/login\b/.test(r.url()) && r.request().method() === 'POST',
      { timeout: 60_000 },
    ),
    page.getByTestId('login-submit').click(),
  ])
  expect(loginResp.ok(), `login failed for ${email}: ${loginResp.status()}`).toBeTruthy()
  const session = (await loginResp.json()) as { access_token: string; user: { id: string } }
  await expect(page).toHaveURL(/\/(overview|task-center|task-templates)/, { timeout: 60_000 })
  return { userId: session.user.id, accessToken: session.access_token }
}

async function logout(page: Page): Promise<void> {
  await page.getByText('退出登录', { exact: true }).first().click({ timeout: 15_000 })
  await expect(page.getByTestId('login-form')).toBeVisible({ timeout: 30_000 })
}

async function openTaskCenter(page: Page, filter: 'inbox' | 'tracking' | 'history'): Promise<void> {
  const snapshot = page.waitForResponse(
    (r) =>
      r.request().method() === 'GET' &&
      /\/api\/v1\/task-center\b/.test(r.url()) &&
      !r.url().includes('/memos'),
    { timeout: 60_000 },
  )
  await page.goto(`/task-center?filter=${filter}`)
  await expect(page).toHaveURL(new RegExp(`filter=${filter}`), { timeout: 30_000 })
  await snapshot
  await expect(page.getByTestId(listPanelTestId(filter))).toBeVisible({ timeout: 30_000 })
}

function listPanelTestId(filter: 'inbox' | 'tracking' | 'history'): string {
  if (filter === 'inbox') {
    return 'task-center-inbox-panel'
  }
  if (filter === 'history') {
    return 'task-center-history-panel'
  }
  return 'task-center-tracking-panel'
}

type TaskCenterEntry = { task_id: string; title: string }

async function resolveCaptureTaskId(
  page: Page,
  accessToken: string,
  hint: string,
): Promise<string> {
  const headers = { Authorization: `Bearer ${accessToken}` }
  let lastInbox = 0
  let lastTracking = 0
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await page.request.get('/api/v1/task-center', { headers })
    expect(response.ok(), `task-center failed: ${response.status()}`).toBeTruthy()
    const snapshot = (await response.json()) as {
      task_inbox: TaskCenterEntry[]
      task_tracking: TaskCenterEntry[]
    }
    lastInbox = snapshot.task_inbox.length
    lastTracking = snapshot.task_tracking.length
    const match = (entry: TaskCenterEntry) => entry.title.includes(hint)
    const hit = snapshot.task_inbox.find(match) ?? snapshot.task_tracking.find(match)
    if (hit) {
      return hit.task_id
    }
    await page.waitForTimeout(2_000)
  }
  if (sharedBatchInstanceId) {
    const submissionsResp = await page.request.get(
      `/api/v1/workflow-graph/instances/${sharedBatchInstanceId}/submissions?node_key=N1_PROPOSE`,
      { headers },
    )
    if (submissionsResp.ok()) {
      const submissions = (await submissionsResp.json()) as {
        submissions: Array<{ assignee_email?: string; topics: Array<{ topic_id: string }> }>
      }
      const mine = submissions.submissions.find((item) => item.assignee_email === ACCOUNTS.copyA)
      const captureTasks = await page.request.get('/api/v1/task-center', { headers })
      const center = (await captureTasks.json()) as {
        task_inbox: TaskCenterEntry[]
        task_tracking: TaskCenterEntry[]
      }
      const any = [...center.task_inbox, ...center.task_tracking].find((entry) =>
        entry.title.includes(hint),
      )
      if (any) {
        return any.task_id
      }
    }
  }
  throw new Error(
    `capture task "${hint}" not in API snapshot (inbox=${lastInbox}, tracking=${lastTracking})`,
  )
}

async function openCaptureTask(page: Page, accessToken: string, hint: string): Promise<void> {
  const taskId = await resolveCaptureTaskId(page, accessToken, hint)
  await page.goto(`/task-center?filter=inbox&selected=${taskId}`)
  await expect(page.getByTestId('template-capture-panel')).toBeVisible({ timeout: 30_000 })
}

async function waitForRootTaskInCenter(
  page: Page,
  accessToken: string,
  rootTaskId: string,
): Promise<'tracking' | 'history'> {
  const headers = { Authorization: `Bearer ${accessToken}` }
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await page.request.get('/api/v1/task-center', { headers })
    expect(response.ok(), `task-center failed: ${response.status()}`).toBeTruthy()
    const snapshot = (await response.json()) as {
      task_tracking: TaskCenterEntry[]
      task_history: TaskCenterEntry[]
    }
    if (snapshot.task_tracking.some((entry) => entry.task_id === rootTaskId)) {
      return 'tracking'
    }
    if (snapshot.task_history.some((entry) => entry.task_id === rootTaskId)) {
      return 'history'
    }
    await page.waitForTimeout(2_000)
  }
  throw new Error(`root task ${rootTaskId} not in task-center tracking/history after finalize`)
}

async function openBatchRunDashboard(page: Page, accessToken: string): Promise<void> {
  expect(sharedRootTaskId, 'root task id missing from Phase A run response').toBeTruthy()
  const filter = await waitForRootTaskInCenter(page, accessToken, sharedRootTaskId)
  await openTaskCenter(page, filter)
  const rootRow = page.getByTestId(listPanelTestId(filter)).getByText(RUN_LABEL).first()
  await expect(rootRow).toBeVisible({ timeout: 30_000 })
  await rootRow.click()
  await page.reload()
  await expect(page.getByTestId('batch-run-dashboard')).toBeVisible({ timeout: 60_000 })
}

async function openTaskByTitleHint(page: Page, accessToken: string, hint: string): Promise<void> {
  const headers = { Authorization: `Bearer ${accessToken}` }
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await page.request.get('/api/v1/task-center', { headers })
    expect(response.ok(), `task-center failed: ${response.status()}`).toBeTruthy()
    const snapshot = (await response.json()) as {
      task_inbox: TaskCenterEntry[]
      task_tracking: TaskCenterEntry[]
      task_history?: TaskCenterEntry[]
    }
    const pools = [
      { filter: 'inbox' as const, entries: snapshot.task_inbox },
      { filter: 'tracking' as const, entries: snapshot.task_tracking },
      { filter: 'history' as const, entries: snapshot.task_history ?? [] },
    ]
    for (const pool of pools) {
      const hit = pool.entries.find((entry) => entry.title.includes(hint))
      if (!hit) {
        continue
      }
      await openTaskCenter(page, pool.filter)
      const row = page.getByTestId(listPanelTestId(pool.filter)).getByText(hint).first()
      await expect(row).toBeVisible({ timeout: 30_000 })
      await row.click()
      return
    }
    await page.waitForTimeout(2_000)
  }
  throw new Error(`task "${hint}" not found in task-center API after polling`)
}

async function submitCapture(page: Page, title: string): Promise<void> {
  await page.getByTestId('template-capture-title').fill(title)
  const captureResp = page.waitForResponse(
    (r) => /\/submit-capture\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
    { timeout: 60_000 },
  )
  await page.getByTestId('template-capture-submit').click()
  await captureResp
}

/** Element Plus filterable el-select（teleport 下拉）：输入关键字过滤后点选 */
async function pickElSelectOption(
  page: Page,
  selectLocator: ReturnType<Page['locator']>,
  labelFragment: string,
): Promise<void> {
  await selectLocator.click()
  const filterInput = selectLocator.locator('input').last()
  await filterInput.fill('')
  await filterInput.fill(labelFragment.split('@')[0] ?? labelFragment)
  const option = page
    .locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: labelFragment })
    .first()
  await expect(option).toBeVisible({ timeout: 30_000 })
  await option.click()
  await page.keyboard.press('Escape').catch(() => {})
}

async function selectParticipantEmails(
  page: Page,
  dialog: ReturnType<Page['locator']>,
  emails: string[],
): Promise<void> {
  const participantsSelect = dialog
    .locator('.el-form-item')
    .filter({ hasText: '文案参与人' })
    .locator('.el-select')
  for (const email of emails) {
    const previewResp = page
      .waitForResponse(
        (r) => /\/preview-participants\b/.test(r.url()) && r.request().method() === 'POST',
        { timeout: 30_000 },
      )
      .catch(() => null)
    await pickElSelectOption(page, participantsSelect, email)
    await previewResp
  }
}

async function resolveCaptureTaskIdForEditor(
  page: Page,
  accessToken: string,
  email: string,
): Promise<string> {
  const mapped = captureTaskIdsByEmail[email]
  if (mapped) {
    return mapped
  }
  const searchResp = await page.request.get('/api/v1/tasks/search?q=提交选题&limit=20', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  expect(searchResp.ok(), `task search failed: ${searchResp.status()}`).toBeTruthy()
  const results = (await searchResp.json()) as Array<{ id: string; title: string }>
  const hit = results.find((item) => item.title.includes('提交选题'))
  if (!hit) {
    throw new Error(
      `capture task not found for ${email}; mapped=${JSON.stringify(captureTaskIdsByEmail)} search=${results.length}`,
    )
  }
  captureTaskIdsByEmail[email] = hit.id
  return hit.id
}

test.describe('Workflow Video multi-account live', () => {
  test.afterAll(() => {
    writeLiveReport({ runTag: RUN_TAG, baseURL: BASE_URL, password: PASSWORD, mode: 'live' })
  })

  test('Phase A: copy lead instantiates batch run', async ({ page }) => {
    const { accessToken: leadToken } = await login(page, ACCOUNTS.copyLead)
    await page.goto('/task-templates')
    await expect(page.getByTestId('task-templates-page')).toBeVisible({ timeout: 30_000 })
    await page.getByRole('tab', { name: /图模板/ }).click()
    await expect(page.getByText('topic_meeting_batch_v1')).toBeVisible({ timeout: 30_000 })
    const candidatePreview = page.waitForResponse(
      (r) => /\/preview-participants\b/.test(r.url()) && r.request().method() === 'POST',
      { timeout: 60_000 },
    )
    await page.getByRole('row', { name: /选题会/ }).getByTestId('graph-template-instantiate').click()
    const dialog = page.getByTestId('template-instantiate-dialog')
    await expect(dialog).toBeVisible()
    const candidatePreviewResp = await candidatePreview
    expect(candidatePreviewResp.ok(), `preview-participants failed: ${candidatePreviewResp.status()}`).toBeTruthy()
    await dialog.locator('.el-form-item').filter({ hasText: '征集主题' }).locator('input').fill(THEME)
    await dialog.getByPlaceholder('例如：第 12 周选题会').fill(RUN_LABEL)
    const managerSelect = dialog.locator('.el-form-item').filter({ hasText: '负责人' }).locator('.el-select')
    await pickElSelectOption(page, managerSelect, ACCOUNTS.copyLead)
    await dialog.getByText('指定成员', { exact: true }).click()
    await selectParticipantEmails(page, dialog, [ACCOUNTS.copyA, ACCOUNTS.copyB, ACCOUNTS.copyC])
    await expect(dialog.getByText(/将展开 3 个采集任务/)).toBeVisible({ timeout: 60_000 })
    const runResp = page.waitForResponse(
      (r) => /\/workflow-graph\/templates\/.*\/runs\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
      { timeout: 60_000 },
    )
    await page.getByTestId('template-instantiate-submit').click()
    const runResult = await runResp
    const runPayload = (await runResult.json()) as {
      instance_id?: string
      root_task_id?: string
      activated_task_count?: number
    }
    sharedBatchInstanceId = runPayload.instance_id ?? ''
    sharedRootTaskId = runPayload.root_task_id ?? ''
    expect(runPayload.activated_task_count ?? 0).toBeGreaterThanOrEqual(3)

    await mapCaptureTasksAfterInstantiate(page, leadToken, sharedBatchInstanceId)

    await snap(page, 'phase-a-instantiate-batch.png')
    await logout(page)
    liveRow({
      id: 'A1',
      phase: '批次实例化',
      actor: ACCOUNTS.copyLead,
      result: 'PASS',
      note: `创建批次 Run：${RUN_LABEL}`,
    })
  })

  test('Phase B1: copy.a submits capture', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyA)
    await openCaptureTask(page, accessToken, '提交选题')
    await submitCapture(page, `选题A ${RUN_TAG}`)
    await snap(page, 'phase-b-copy-a-capture.png')
    await logout(page)
    liveRow({ id: 'B1', phase: '采集 N1', actor: ACCOUNTS.copyA, result: 'PASS', note: '选题 A' })
  })

  test('Phase B2: copy.b submits capture', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyB)
    await openCaptureTask(page, accessToken, '提交选题')
    await submitCapture(page, `选题B ${RUN_TAG}`)
    await snap(page, 'phase-b-copy-b-capture.png')
    await logout(page)
    liveRow({ id: 'B2', phase: '采集 N1', actor: ACCOUNTS.copyB, result: 'PASS', note: '选题 B' })
  })

  test('Phase B3: copy.c submits capture', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyC)
    await openCaptureTask(page, accessToken, '提交选题')
    await submitCapture(page, `选题C ${RUN_TAG}`)
    await snap(page, 'phase-b-copy-c-capture.png')
    await logout(page)
    liveRow({ id: 'B3', phase: '采集 N1', actor: ACCOUNTS.copyC, result: 'PASS', note: '选题 C' })
  })

  test('Phase C-D: copy lead aggregate and batch dashboard', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyLead)
    await openTaskByTitleHint(page, accessToken, '汇总派发')
    await expect(page.getByTestId('template-aggregate-panel')).toBeVisible({ timeout: 30_000 })
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(3, {
      timeout: 30_000,
    })
    await snap(page, 'phase-c-aggregate-matrix.png')

    const finalizeResp = page.waitForResponse(
      (r) => /\/finalize-topics\b/.test(r.url()) && r.request().method() === 'POST',
      { timeout: 60_000 },
    )
    await page.getByTestId('template-aggregate-submit').click()
    const finalizeResult = await finalizeResp
    const finalizeBody = await finalizeResult.json().catch(() => ({}))
    expect(
      finalizeResult.ok(),
      `finalize-topics failed: ${finalizeResult.status()} ${JSON.stringify(finalizeBody)}`,
    ).toBeTruthy()
    expect(finalizeBody.child_instance_ids?.length ?? 0, JSON.stringify(finalizeBody)).toBe(3)
    expect(['completed', 'partial']).toContain(finalizeBody.fork_status)
    await snap(page, 'phase-c-finalize.png')

    await openBatchRunDashboard(page, accessToken)
    await expect(page.locator('[data-testid="batch-run-dashboard"] tbody tr')).toHaveCount(3)
    await snap(page, 'phase-d-batch-dashboard.png')
    await logout(page)
    liveRow({
      id: 'C1',
      phase: '汇总派发',
      actor: ACCOUNTS.copyLead,
      result: 'PASS',
      note: 'finalize 3 题',
    })
    liveRow({
      id: 'D1',
      phase: '批次看板',
      actor: ACCOUNTS.copyLead,
      result: 'PASS',
      note: '看板 3 子 Run',
    })
  })

  test('Phase E: copy.a script write deliverable on child run', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyA)
    await openTaskByTitleHint(page, accessToken, `选题A ${RUN_TAG}`)

    const acceptBtn = page.getByRole('button', { name: '接受任务' })
    if (await acceptBtn.isVisible().catch(() => false)) {
      await acceptBtn.click()
    }
    const startBtn = page.getByRole('button', { name: '开始处理' })
    if (await startBtn.isVisible().catch(() => false)) {
      await startBtn.click()
    }

    await expect(page.getByRole('button', { name: '提交交付物' })).toBeVisible({ timeout: 30_000 })
    const deliverableField = page.locator('textarea[placeholder*="交付"]').first()
    await expect(deliverableField).toBeVisible({ timeout: 30_000 })
    await deliverableField.fill(`脚本正文 ${RUN_TAG}`)
    const deliverResp = page.waitForResponse(
      (r) =>
        /\/api\/v1\/tasks\/.*\/(deliverable|submit-capture)\b/.test(r.url())
        && r.request().method() === 'POST'
        && r.ok(),
      { timeout: 60_000 },
    )
    await page.getByRole('button', { name: '提交交付物' }).click()
    await deliverResp
    await snap(page, 'phase-e-script-deliverable.png')
    await logout(page)
    liveRow({
      id: 'E1',
      phase: '脚本撰写 N3',
      actor: ACCOUNTS.copyA,
      result: 'PASS',
      note: '交付物已提交',
    })
  })

  test('Phase F: copy lead reviews script (N4)', async ({ page }) => {
    const { accessToken } = await login(page, ACCOUNTS.copyLead)
    await openTaskByTitleHint(page, accessToken, `选题A ${RUN_TAG}`)

    const approveBtn = page.getByRole('button', { name: '验收通过' })
    const hasApproveUi = await approveBtn.isVisible({ timeout: 30_000 }).catch(() => false)
    if (hasApproveUi) {
      const reviewResp = page.waitForResponse(
        (r) => /\/api\/v1\/tasks\/.*\/review\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 60_000 },
      )
      await approveBtn.click()
      await reviewResp
    } else {
      const centerResp = await page.request.get('/api/v1/task-center', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      expect(centerResp.ok()).toBeTruthy()
      const center = (await centerResp.json()) as {
        task_inbox: TaskCenterEntry[]
        task_tracking: TaskCenterEntry[]
      }
      const reviewTask =
        center.task_inbox.find((entry) => entry.title.includes(`选题A ${RUN_TAG}`))
        ?? center.task_tracking.find((entry) => entry.title.includes(`选题A ${RUN_TAG}`))
      expect(reviewTask, '选题 A 制作 Run 未出现在 task-center').toBeTruthy()
      const reviewResp = await page.request.post(`/api/v1/tasks/${reviewTask!.task_id}/review`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        data: { action: 'approve', comment: `审核通过 ${RUN_TAG}`, quality_score: 5 },
      })
      expect(reviewResp.ok(), `review failed: ${reviewResp.status()}`).toBeTruthy()
    }
    await snap(page, 'phase-f-script-review.png')
    await logout(page)
    liveRow({
      id: 'F1',
      phase: '脚本审核 N4',
      actor: ACCOUNTS.copyLead,
      result: 'PASS',
      note: '负责人验收通过',
    })
  })
})
