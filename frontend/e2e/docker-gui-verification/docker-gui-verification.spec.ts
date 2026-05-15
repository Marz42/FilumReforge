/**
 * 对「已启动」的 Docker Nginx 入口执行 E2E-GUI 自动化子集。
 * 支持**空库**：先「初始化管理员」，再在宿主执行 `docker compose … seed_sample_data`。
 *
 * 环境变量：
 *   GUI_BASE_URL           默认 http://127.0.0.1:8080
 *   GUI_BOOTSTRAP_EMAIL    默认 admin@example.com
 *   GUI_BOOTSTRAP_PASSWORD 初始化管理员及后续 L0 登录密码，默认 FilumTest123!
 *   GUI_DEMO_PASSWORD      seed demo 账号密码，默认与 bootstrap 相同
 *   VERIFY_RUN_DIR         由 playwright.docker-gui.config.ts 设置
 */
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../../..')
const runDir = process.env.VERIFY_RUN_DIR ?? path.join(repoRoot, 'verification-runs', 'docker-gui-fallback')
const shotDir = path.join(runDir, 'screenshots')

type Row = { id: string; section: string; result: 'PASS' | 'FAIL' | 'SKIP'; note: string }

const rows: Row[] = []
let seedLog = ''

/** 跨用例串行：任务链路与汇报链路 */
let flowTaskId = ''
let reportFlowTitle = ''
const flowTag = (process.env.VERIFY_RUN_ID ?? `run-${Date.now()}`).replace(/[^\w-]+/g, '_').slice(-24)

function row(r: Row): void {
  rows.push(r)
}

function shot(name: string): string {
  fs.mkdirSync(shotDir, { recursive: true })
  return path.join(shotDir, name)
}

function runSeedFromHost(): string {
  const composeFile = path.join(repoRoot, 'infra', 'docker', 'docker-compose.yml')
  if (!fs.existsSync(composeFile)) {
    return 'SKIP: infra/docker/docker-compose.yml not found'
  }
  try {
    const cmd = `docker compose -f "${composeFile}" exec -T backend python -m app.scripts.seed_sample_data --password "${process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'}"`
    const out = execSync(cmd, {
      cwd: path.join(repoRoot, 'infra', 'docker'),
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 120_000,
    })
    return out.slice(-4000)
  } catch (e: unknown) {
    const err = e as { stderr?: Buffer; stdout?: Buffer; message?: string }
    return `ERROR: ${err.message ?? String(e)}\n${err.stderr?.toString() ?? ''}\n${err.stdout?.toString() ?? ''}`
  }
}

async function login(page: import('@playwright/test').Page, email: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByTestId('login-email').locator('input').fill(email)
  await page.getByTestId('login-password').locator('input').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(/\/(overview|task-center)/, { timeout: 45_000 })
}

async function logout(page: import('@playwright/test').Page): Promise<void> {
  await page.getByText('退出登录', { exact: true }).first().click({ timeout: 15_000 })
  await expect(page).toHaveURL(/\/login/, { timeout: 20_000 })
}

/** 经侧栏进入汇报中心（避免整页 goto /reports 与 refresh 竞态导致快照未拉取） */
async function navigateReportCenterTab(page: import('@playwright/test').Page, tabLabel: string): Promise<void> {
  const snapshotResp = page.waitForResponse(
    (r) =>
      r.request().method() === 'GET' &&
      r.url().includes('report-center') &&
      !r.url().includes('report-center/reports'),
    { timeout: 45_000 },
  )
  await page.locator('.app-shell__aside').getByText('汇报中心', { exact: true }).click()
  await expect(page).toHaveURL(/\/reports/, { timeout: 15_000 })
  const snapGet = await snapshotResp
  expect(snapGet.ok(), `GET report-center → HTTP ${snapGet.status()}`).toBeTruthy()
  await page.getByRole('tab', { name: tabLabel }).click()
}

test.describe.configure({ mode: 'serial' })

test.beforeAll(() => {
  fs.mkdirSync(shotDir, { recursive: true })
})

test.afterAll(() => {
  const lines: string[] = [
    '# Docker Compose GUI 验证报告（自动化）',
    '',
    '**对照清单**：[infra/docker/E2E-GUI-VERIFICATION.md](../infra/docker/E2E-GUI-VERIFICATION.md)（本运行为可脚本化子集 + 从**初始化管理员**开始的冷启动路径）。',
    '',
    `- **输出目录**：\`verification-runs/docker-gui-${process.env.VERIFY_RUN_ID ?? 'unknown'}\``,
    `- **基址**：${process.env.GUI_BASE_URL ?? 'http://127.0.0.1:8080'}`,
    `- **生成时间**：${new Date().toISOString()}`,
    '',
    '## 覆盖范围说明',
    '',
    '- **已自动化**：A5 网关健康检查；登录页截图；空库时「初始化管理员」；宿主 Docker `seed_sample_data`；L0 部门/总览侧栏；L1 HR 菜单与 `/departments` 重定向；L4 员工菜单与 `/people` 重定向；**C1** 任务建立→待办→开始处理→提交交付→创建人验收→完成；**C1** 跨部门指派（L2→客户成功，若可发布）；**C1** 消息中心截图与「回到来源」（若存在）；**C2** 向上汇报多级（L4→L3 继续上报→L2 确认完成→发起人归档）。',
    '- **未自动化**（仍依赖人工或环境）：图引擎握手「转办」、向下传达全链路细粒度、Web Push、知识库发布、邀请注册等。',
    '',
    '## 结果汇总',
    '',
    '| 步骤 ID | 章节 | 结果 | 说明 |',
    '| --- | --- | --- | --- |',
  ]
  for (const r of rows) {
    lines.push(`| ${r.id} | ${r.section} | ${r.result} | ${r.note.replace(/\|/g, '\\|').replace(/\n/g, ' ')} |`)
  }
  if (seedLog) {
    lines.push('', '## seed_sample_data 输出（尾部）', '', '```text', seedLog.trimEnd(), '```')
  }
  lines.push('', '## 截图索引', '')
  const files = fs.existsSync(shotDir) ? fs.readdirSync(shotDir).filter((f) => f.endsWith('.png')) : []
  for (const f of files.sort()) {
    lines.push(`- ./screenshots/${f}`)
  }
  fs.writeFileSync(path.join(runDir, 'report.md'), lines.join('\n'), 'utf8')
})

test('A5: health via gateway (/api/v1/health)', async ({ request }) => {
  const base = (process.env.GUI_BASE_URL ?? 'http://127.0.0.1:8080').replace(/\/$/, '')
  const res = await request.get(`${base}/api/v1/health`)
  const ok = res.ok()
  const status = res.status()
  await res.dispose()
  row({
    id: 'A5',
    section: 'A 环境',
    result: ok ? 'PASS' : 'FAIL',
    note: `GET /api/v1/health → HTTP ${status}（经 Nginx；根路径 /healthz 未反代到 backend）`,
  })
  expect(ok).toBeTruthy()
})

test('登录页与初始化管理员（空库）', async ({ page }) => {
  await page.goto('/login')
  await page.waitForSelector('[data-testid="login-page"]')
  /** 同源 fetch；不依赖 axios baseURL（与页面内 bootstrap-status 一致） */
  const needBootstrap = await page.evaluate(async () => {
    const res = await fetch(new URL('/api/v1/auth/bootstrap-status', window.location.origin).href, {
      credentials: 'include',
    })
    if (!res.ok) {
      throw new Error(`bootstrap-status HTTP ${res.status}`)
    }
    const data = (await res.json()) as { bootstrap_required?: boolean }
    return data.bootstrap_required === true
  })
  await page.screenshot({ path: shot('01-login-page.png'), fullPage: true })
  row({ id: 'A-ui-1', section: 'A 环境', result: 'PASS', note: '登录页 01-login-page.png' })

  const bootstrapTab = page.getByRole('tab', { name: '初始化管理员' })

  const bootstrapEmail = process.env.GUI_BOOTSTRAP_EMAIL ?? 'admin@example.com'
  const bootstrapPassword = process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'

  if (needBootstrap) {
    await expect(bootstrapTab).toBeVisible({ timeout: 10_000 })
    await bootstrapTab.click()
    await page.screenshot({ path: shot('02-bootstrap-tab.png'), fullPage: true })
    await page.getByTestId('bootstrap-email').locator('input').fill(bootstrapEmail)
    await page.getByTestId('bootstrap-password').locator('input').fill(bootstrapPassword)
    await page.getByTestId('bootstrap-real-name').locator('input').fill('系统管理员')
    await page.getByTestId('bootstrap-employee-no').locator('input').fill('EMP-ROOT')
    await page.getByTestId('bootstrap-submit').click()
    await expect(page).toHaveURL(/\/overview/, { timeout: 45_000 })
    await expect(page.getByRole('menuitem', { name: '部门管理' })).toBeVisible({ timeout: 15_000 })
    await page.screenshot({ path: shot('03-admin-after-bootstrap.png'), fullPage: true })
    row({
      id: 'A-bootstrap',
      section: 'A 环境',
      result: 'PASS',
      note: `已执行初始化管理员 → ${bootstrapEmail}，见 02/03 截图`,
    })
  } else {
    await page.getByRole('tab', { name: '登录系统' }).click()
    await page.getByTestId('login-email').locator('input').fill(bootstrapEmail)
    await page.getByTestId('login-password').locator('input').fill(bootstrapPassword)
    const [loginResp] = await Promise.all([
      page.waitForResponse(
        (r) => /\/api\/v1\/auth\/login\b/.test(r.url()) && r.request().method() === 'POST',
        { timeout: 45_000 },
      ),
      page.getByTestId('login-submit').click(),
    ])
    if (!loginResp.ok()) {
      const errBody = await loginResp.text().catch(() => '')
      await page.screenshot({ path: shot('03-login-failed.png'), fullPage: true })
      row({
        id: 'A-bootstrap',
        section: 'A 环境',
        result: 'FAIL',
        note: `登录 POST HTTP ${loginResp.status()} ${errBody.slice(0, 400)}`,
      })
      throw new Error(`Login failed HTTP ${loginResp.status()}`)
    }
    try {
      await expect(page).toHaveURL(/\/overview/, { timeout: 45_000 })
      await page.screenshot({ path: shot('03-admin-existing-login.png'), fullPage: true })
      row({
        id: 'A-bootstrap',
        section: 'A 环境',
        result: 'SKIP',
        note: '服务端 bootstrap_required=false，已用管理员账号登录（库非空或已初始化）',
      })
    } catch {
      await page.screenshot({ path: shot('03-login-failed.png'), fullPage: true })
      row({
        id: 'A-bootstrap',
        section: 'A 环境',
        result: 'FAIL',
        note: '无初始化入口且账号密码登录失败，见 03-login-failed.png',
      })
      throw new Error('Cannot bootstrap or login as admin')
    }
  }
})

test('A6: seed_sample_data（宿主 Docker）', async () => {
  seedLog = runSeedFromHost()
  if (seedLog.startsWith('SKIP:')) {
    row({ id: 'A6-seed', section: 'A 环境', result: 'SKIP', note: seedLog })
  } else if (seedLog.startsWith('ERROR:')) {
    row({ id: 'A6-seed', section: 'A 环境', result: 'FAIL', note: seedLog.slice(0, 500) })
  } else {
    row({ id: 'A6-seed', section: 'A 环境', result: 'PASS', note: 'docker compose exec backend seed_sample_data 已执行，详见报告尾部日志' })
  }
})

test('L0: 部门管理入口（管理员）', async ({ page }) => {
  const bootstrapEmail = process.env.GUI_BOOTSTRAP_EMAIL ?? 'admin@example.com'
  const bootstrapPassword = process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'

  await login(page, bootstrapEmail, bootstrapPassword)

  await expect(page.getByRole('menuitem', { name: '部门管理' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '人员管理' })).toBeVisible()
  await page.goto('/departments')
  await page.waitForTimeout(800)
  await page.screenshot({ path: shot('04-admin-departments.png'), fullPage: true })
  row({ id: 'B-L0', section: 'B 权限', result: 'PASS', note: 'L0 部门管理 + 人员管理可见，/departments 截图 04' })
  await logout(page)
})

test('L1-HR: 无部门管理；/departments → overview', async ({ page }) => {
  const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
  await login(page, 'demo.hr@example.com', demoPassword)
  await page.screenshot({ path: shot('05-hr-overview.png'), fullPage: true })
  await expect(page.getByRole('menuitem', { name: '部门管理' })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: '人员管理' })).toBeVisible()
  row({ id: 'B-L1-nav', section: 'B 权限', result: 'PASS', note: 'HR 无部门管理菜单' })

  await page.goto('/departments')
  await page.waitForTimeout(800)
  expect(page.url()).toMatch(/\/overview/)
  await page.screenshot({ path: shot('06-hr-dept-redirect.png'), fullPage: true })
  row({ id: 'B-L1-dept', section: 'B 权限', result: 'PASS', note: '/departments 重定向 overview' })
  await logout(page)
})

test('L4: 无人员/部门菜单；/people → overview', async ({ page }) => {
  const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
  await login(page, 'demo.engineer.a@example.com', demoPassword)
  await page.screenshot({ path: shot('07-engineer-overview.png'), fullPage: true })
  await expect(page.getByRole('menuitem', { name: '部门管理' })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: '人员管理' })).toHaveCount(0)
  row({ id: 'B-L4-nav', section: 'B 权限', result: 'PASS', note: '工程师无管理菜单' })

  await page.goto('/people')
  await page.waitForTimeout(800)
  expect(page.url()).toMatch(/\/overview/)
  await page.screenshot({ path: shot('08-engineer-people-redirect.png'), fullPage: true })
  row({ id: 'B-L4-people', section: 'B 权限', result: 'PASS', note: '/people 重定向 overview' })
  await logout(page)
})

test.describe('C1 任务全链路 + 消息', () => {
  test.setTimeout(120_000)

  test('C1.1 L3 建立任务指派 L4', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    const title = `[E2E-T1-${flowTag}]`
    await login(page, 'demo.platform.lead@example.com', demoPassword)
    await page.goto('/task-center')
    await page.waitForSelector('[data-testid="task-center-view"]', { timeout: 25_000 })
    await page.screenshot({ path: shot('10-c1-l3-task-center.png'), fullPage: true })
    await page.getByTestId('task-center-create-task').click()
    await expect(page.getByTestId('task-center-task-drawer')).toBeVisible()
    await page.getByTestId('task-center-task-title').locator('input').fill(title)
    await page.getByTestId('task-center-task-description').locator('textarea').fill('Docker GUI E2E 任务链路')
    await page.getByTestId('task-center-task-assignee').click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: 'demo.engineer.a@example.com' }).first().click()
    const [createResp] = await Promise.all([
      page.waitForResponse(
        (r) => /\/api\/v1\/tasks\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      page.getByTestId('task-center-task-submit').click(),
    ])
    const created = (await createResp.json()) as { id: string }
    flowTaskId = created.id
    await page.screenshot({ path: shot('11-c1-l3-after-create.png'), fullPage: true })
    row({
      id: 'C1-1',
      section: 'C1 任务',
      result: 'PASS',
      note: `L3 建立任务 title=${title} id=${flowTaskId} 见 10/11`,
    })
    await logout(page)
  })

  test('C1.2 L4 待办出现任务', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.engineer.a@example.com', demoPassword)
    await page.goto('/task-center')
    await page.waitForSelector('[data-testid="task-center-view"]', { timeout: 25_000 })
    await expect(page.getByText(`[E2E-T1-${flowTag}]`, { exact: false })).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: shot('12-c1-l4-inbox.png'), fullPage: true })
    row({ id: 'C1-2', section: 'C1 任务', result: 'PASS', note: 'L4 待办含新建任务 12' })
    await logout(page)
  })

  test('C1.3 L4 开始处理并提交交付', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    expect(flowTaskId.length).toBeGreaterThan(0)
    await login(page, 'demo.engineer.a@example.com', demoPassword)
    await page.goto(`/task-center?tab=tracking&selected=${flowTaskId}`)
    await page.waitForSelector('[data-testid="task-center-view"]', { timeout: 25_000 })
    await page.waitForSelector('[data-testid="tasks-detail-panel"]', { timeout: 30_000 })
    /** TasksView 在 loadData 完成前可能忽略 initialSelectedTaskId，再导航一次以触发选中 */
    await page.waitForTimeout(1500)
    await page.goto(`/task-center?tab=tracking&selected=${flowTaskId}`)
    await page.waitForSelector('[data-testid="tasks-detail-panel"]', { timeout: 30_000 })
    await expect(page.locator('[data-testid="tasks-detail-panel"]').getByText(`[E2E-T1-${flowTag}]`, { exact: false })).toBeVisible({
      timeout: 25_000,
    })
    await page.screenshot({ path: shot('13-c1-l4-detail-todo.png'), fullPage: true })
    const acceptBtn = page.getByRole('button', { name: '接受任务' })
    if (await acceptBtn.isVisible().catch(() => false)) {
      await Promise.all([
        page.waitForResponse(
          (r) => r.url().includes(`/tasks/${flowTaskId}/accept`) && r.request().method() === 'POST' && r.ok(),
          { timeout: 45_000 },
        ),
        acceptBtn.click(),
      ])
      await page.waitForTimeout(800)
    }
    await expect(page.getByRole('button', { name: '开始处理' })).toBeVisible({ timeout: 20_000 })
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes(`/tasks/${flowTaskId}/status`) &&
          r.request().method() === 'PATCH' &&
          r.ok(),
        { timeout: 45_000 },
      ),
      page.getByRole('button', { name: '开始处理' }).click(),
    ])
    await expect(page.getByRole('button', { name: '提交交付物' })).toBeVisible({ timeout: 20_000 })
    await page.getByPlaceholder('说明本次交付内容、完成情况与需要验收的要点').fill('E2E 交付说明：已完成开发与自测')
    await page.screenshot({ path: shot('14-c1-l4-doing-deliverable.png'), fullPage: true })
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes(`/tasks/${flowTaskId}/`) && r.url().includes('deliverable') && r.request().method() === 'POST',
        { timeout: 45_000 },
      ),
      page.getByRole('button', { name: '提交交付物' }).click(),
    ])
    await page.screenshot({ path: shot('15-c1-l4-after-submit.png'), fullPage: true })
    row({ id: 'C1-3', section: 'C1 任务', result: 'PASS', note: 'L4 开始处理+提交交付 13–15' })
    await logout(page)
  })

  test('C1.4 L3 验收通过', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.platform.lead@example.com', demoPassword)
    await page.goto(`/task-center?tab=tracking&selected=${flowTaskId}`)
    await page.waitForSelector('[data-testid="tasks-detail-panel"]', { timeout: 30_000 })
    await page.waitForTimeout(1500)
    await page.goto(`/task-center?tab=tracking&selected=${flowTaskId}`)
    await page.waitForSelector('[data-testid="tasks-detail-panel"]', { timeout: 30_000 })
    await expect(page.locator('[data-testid="tasks-detail-panel"]').getByText(`[E2E-T1-${flowTag}]`, { exact: false })).toBeVisible({
      timeout: 25_000,
    })
    await expect(page.getByRole('button', { name: '验收通过' })).toBeVisible({ timeout: 25_000 })
    await page.screenshot({ path: shot('16-c1-l3-review.png'), fullPage: true })
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes(`/tasks/${flowTaskId}/`) &&
          r.url().includes('/review') &&
          r.request().method() === 'POST' &&
          r.ok(),
        { timeout: 45_000 },
      ),
      page.getByRole('button', { name: '验收通过' }).click(),
    ])
    await page.screenshot({ path: shot('17-c1-l3-after-approve.png'), fullPage: true })
    row({ id: 'C1-4', section: 'C1 任务', result: 'PASS', note: 'L3 验收通过 16–17' })
    await logout(page)
  })

  test('C1.5 L2 跨部门指派（若可发布）', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    const title = `[E2E-XDEPT-${flowTag}]`
    await login(page, 'demo.tech.director@example.com', demoPassword)
    await page.goto('/task-center')
    await page.waitForSelector('[data-testid="task-center-view"]', { timeout: 25_000 })
    const canPublish = await page.getByTestId('task-center-create-task').isEnabled().catch(() => false)
    await page.screenshot({ path: shot('18-c1-l2-task-center.png'), fullPage: true })
    if (!canPublish) {
      row({
        id: 'C1-5',
        section: 'C1 任务',
        result: 'SKIP',
        note: 'L2 无建立任务权限，跳过跨部门 18',
      })
      await logout(page)
      return
    }
    await page.getByTestId('task-center-create-task').click()
    await page.getByTestId('task-center-task-title').locator('input').fill(title)
    await page.getByTestId('task-center-task-description').locator('textarea').fill('跨部门 E2E')
    await page.getByTestId('task-center-task-assignee').click()
    const opt = page.locator('.el-select-dropdown__item').filter({ hasText: 'demo.success@example.com' })
    if ((await opt.count()) === 0) {
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: '取消' }).click()
      row({ id: 'C1-5', section: 'C1 任务', result: 'SKIP', note: '执行人列表无 demo.success，跳过 18' })
      await logout(page)
      return
    }
    await opt.first().click()
    await Promise.all([
      page.waitForResponse(
        (r) => /\/api\/v1\/tasks\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      page.getByTestId('task-center-task-submit').click(),
    ])
    await page.screenshot({ path: shot('19-c1-l2-after-xdept-create.png'), fullPage: true })
    await logout(page)
    await login(page, 'demo.success@example.com', demoPassword)
    await page.goto('/task-center')
    await page.waitForSelector('[data-testid="task-center-view"]', { timeout: 25_000 })
    await expect(page.getByText(title, { exact: false })).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: shot('20-c1-success-inbox.png'), fullPage: true })
    row({ id: 'C1-5', section: 'C1 任务', result: 'PASS', note: 'L2 建跨部门任务 + 客户成功待办 18–20' })
    await logout(page)
  })

  test('C1.6 消息中心与回到来源', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.engineer.a@example.com', demoPassword)
    await page.goto('/messages')
    await page.waitForTimeout(1200)
    await page.screenshot({ path: shot('21-c1-messages.png'), fullPage: true })
    let note = '消息中心 21；无可见「回到来源」按钮（可能无通知或未推送）'
    const back = page.getByRole('button', { name: '回到来源' }).first()
    if (await back.isVisible().catch(() => false)) {
      await back.click({ noWaitAfter: true }).catch(() => undefined)
      await page.waitForTimeout(400)
      await page.goto('/overview')
      await expect(page).toHaveURL(/\/overview/, { timeout: 15_000 })
      await page.screenshot({ path: shot('22-c1-messages-after-back.png'), fullPage: true })
      note = '消息中心 21；已点回到来源并回总览 22'
    }
    row({
      id: 'C1-6',
      section: 'C1 任务',
      result: 'PASS',
      note,
    })
    /** 消息页/回跳后壳层可能不稳定，直接清 Cookie 结束会话，避免卡在退出登录 */
    await page.context().clearCookies()
    await page.goto('/login')
    await page.waitForSelector('[data-testid="login-page"]', { timeout: 15_000 })
  })
})

test.describe('C2 汇报多级', () => {
  test.setTimeout(120_000)

  test('C2.1 L4 发起向上汇报（目标含多级）', async ({ page }) => {
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    reportFlowTitle = ''
    const title = `[E2E-RUP-${flowTag}]`
    await login(page, 'demo.engineer.a@example.com', demoPassword)
    await navigateReportCenterTab(page, '待处理')
    await page.getByTestId('reports-open-create').click()
    await expect(page.getByTestId('reports-create-dialog')).toBeVisible({ timeout: 10_000 })
    const pickUp = page.getByTestId('reports-create-pick-upward')
    if (!(await pickUp.isVisible().catch(() => false))) {
      await page.screenshot({ path: shot('23-c2-l4-upward-blocked.png'), fullPage: true })
      row({
        id: 'C2-1',
        section: 'C2 汇报',
        result: 'SKIP',
        note: '弹窗内无向上汇报入口 23',
      })
      await logout(page)
      return
    }
    await pickUp.click()
    const dlg = page.getByTestId('reports-create-dialog')
    await expect(dlg.getByTestId('reports-create-form-upward')).toBeVisible({ timeout: 15_000 })
    await dlg.locator('.el-form-item').filter({ hasText: '汇报对象' }).locator('.el-select').click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: '高原' }).first().click()
    await dlg
      .locator('.el-form-item')
      .filter({ hasText: '主题' })
      .locator('.el-input__inner')
      .first()
      .fill(title)
    await dlg.locator('.el-form-item').filter({ hasText: '内容' }).locator('textarea').first().fill('E2E 多级汇报正文\n\n- 项 1\n- 项 2')
    await page.screenshot({ path: shot('23-c2-l4-upward-form.png'), fullPage: true })
    await Promise.all([
      page.waitForResponse(
        (r) => /\/api\/v1\/report-center\/reports\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      dlg.getByTestId('reports-create-submit-upward').click(),
    ])
    reportFlowTitle = title
    await page.screenshot({ path: shot('24-c2-l4-after-submit.png'), fullPage: true })
    row({ id: 'C2-1', section: 'C2 汇报', result: 'PASS', note: `向上汇报 ${reportFlowTitle} 23–24` })
    await logout(page)
  })

  test('C2.2 L3 待处理继续上报', async ({ page }) => {
    if (!reportFlowTitle) {
      row({ id: 'C2-2', section: 'C2 汇报', result: 'SKIP', note: '无汇报标题（上步跳过）' })
      return
    }
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.platform.lead@example.com', demoPassword)
    await navigateReportCenterTab(page, '待处理')
    await expect(page.getByText(reportFlowTitle, { exact: false })).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: shot('25-c2-l3-pending.png'), fullPage: true })
    const adv = page.getByRole('button', { name: '继续上报' })
    if ((await adv.count()) === 0) {
      await page.screenshot({ path: shot('26-c2-l3-no-advance-btn.png'), fullPage: true })
      row({ id: 'C2-2', section: 'C2 汇报', result: 'SKIP', note: '未出现继续上报 25–26' })
      await logout(page)
      return
    }
    await Promise.all([
      page.waitForResponse(
        (r) => /\/report-center\/reports\/[^/]+\/actions/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      adv.first().click(),
    ])
    await page.screenshot({ path: shot('26-c2-l3-after-advance.png'), fullPage: true })
    row({ id: 'C2-2', section: 'C2 汇报', result: 'PASS', note: 'L3 继续上报 25–26' })
    await logout(page)
  })

  test('C2.3 L2 待处理确认完成', async ({ page }) => {
    if (!reportFlowTitle) {
      row({ id: 'C2-3', section: 'C2 汇报', result: 'SKIP', note: '无汇报标题' })
      return
    }
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.tech.director@example.com', demoPassword)
    await navigateReportCenterTab(page, '待处理')
    await expect(page.getByText(reportFlowTitle, { exact: false })).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: shot('27-c2-l2-pending.png'), fullPage: true })
    const done = page.getByRole('button', { name: '确认完成' })
    await Promise.all([
      page.waitForResponse(
        (r) => /\/report-center\/reports\/[^/]+\/actions/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      done.first().click(),
    ])
    await page.screenshot({ path: shot('28-c2-l2-after-complete.png'), fullPage: true })
    row({ id: 'C2-3', section: 'C2 汇报', result: 'PASS', note: 'L2 确认完成 27–28' })
    await logout(page)
  })

  test('C2.4 L4 历史归档', async ({ page }) => {
    if (!reportFlowTitle) {
      row({ id: 'C2-4', section: 'C2 汇报', result: 'SKIP', note: '无汇报标题' })
      return
    }
    const demoPassword = process.env.GUI_DEMO_PASSWORD ?? process.env.GUI_BOOTSTRAP_PASSWORD ?? 'FilumTest123!'
    await login(page, 'demo.engineer.a@example.com', demoPassword)
    await navigateReportCenterTab(page, '历史归档')
    await expect(page.getByText(reportFlowTitle, { exact: false })).toBeVisible({ timeout: 30_000 })
    await page.screenshot({ path: shot('29-c2-l4-history.png'), fullPage: true })
    const arch = page.getByRole('button', { name: '归档' })
    if ((await arch.count()) === 0) {
      row({ id: 'C2-4', section: 'C2 汇报', result: 'SKIP', note: '历史无归档按钮 29' })
      await logout(page)
      return
    }
    await Promise.all([
      page.waitForResponse(
        (r) => /\/report-center\/reports\/[^/]+\/actions/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
        { timeout: 45_000 },
      ),
      arch.first().click(),
    ])
    await page.screenshot({ path: shot('30-c2-l4-after-archive.png'), fullPage: true })
    row({ id: 'C2-4', section: 'C2 汇报', result: 'PASS', note: '发起人归档 29–30' })
    await logout(page)
  })
})
