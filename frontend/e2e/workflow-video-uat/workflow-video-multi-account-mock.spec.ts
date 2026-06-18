/**

 * 视频制作全流程 · 多账号 Mock E2E（无 Docker，与 Live spec 阶段 A–F 对齐）

 */

import { expect, test, type Page } from '@playwright/test'



import { liveRow, liveShot, writeLiveReport } from '../live/workflow-video-live-report.ts'

import {

  installWorkflowVideoMockApi,

  loginAs,

  resetVideoMockForMultiAccount,

  videoMockState,

  VIDEO_DEMO_ACCOUNTS,

} from '../workflow-video-mock.ts'



const ACCOUNTS = VIDEO_DEMO_ACCOUNTS

const PASSWORD = 'secret-password'

const RUN_TAG = `mock-${Date.now()}`

const THEME = `E2E多账号全流程 ${RUN_TAG}`

const RUN_LABEL = `批次 ${RUN_TAG}`



test.describe.configure({ mode: 'serial' })



test.beforeEach(async ({ page }) => {

  await installWorkflowVideoMockApi(page)

})



async function snap(page: Page, file: string): Promise<void> {

  await page.screenshot({ path: liveShot(file), fullPage: true })

}



async function logout(page: Page): Promise<void> {

  await page.getByText('退出登录', { exact: true }).first().click({ timeout: 15_000 })

  await expect(page.getByTestId('login-form')).toBeVisible({ timeout: 30_000 })

}



async function openTaskCenter(page: Page, filter: 'inbox' | 'tracking'): Promise<void> {
  await page.goto(`/task-center?filter=${filter}`)
  await expect(page).toHaveURL(new RegExp(`filter=${filter}`), { timeout: 30_000 })
  await expect(page.getByTestId(listPanelTestId(filter))).toBeVisible({ timeout: 30_000 })
}



function listPanelTestId(filter: 'inbox' | 'tracking'): string {

  return filter === 'inbox' ? 'task-center-inbox-panel' : 'task-center-tracking-panel'

}



async function openCaptureTask(page: Page, hint: string): Promise<void> {

  await openTaskCenter(page, 'inbox')

  const row = page.getByTestId(listPanelTestId('inbox')).getByText(hint).first()

  await expect(row).toBeVisible({ timeout: 30_000 })

  await row.click()

  await expect(page.getByTestId('template-capture-panel')).toBeVisible({ timeout: 30_000 })

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



test.describe('Workflow Video multi-account mock', () => {

  test.afterAll(() => {

    writeLiveReport({

      runTag: RUN_TAG,

      baseURL: 'http://127.0.0.1:4173',

      password: PASSWORD,

      mode: 'mock',

    })

  })



  test('Phase A: copy lead instantiates batch run', async ({ page }) => {

    resetVideoMockForMultiAccount(RUN_LABEL)

    await loginAs(page, ACCOUNTS.copyLead, PASSWORD)

    await page.goto('/task-templates')
    await expect(page.getByTestId('task-templates-page')).toBeVisible({ timeout: 30_000 })
    await page.getByRole('tab', { name: /图模板/ }).click()

    await expect(page.getByText('topic_meeting_batch_v1')).toBeVisible({ timeout: 30_000 })

    await page.getByRole('row', { name: /选题会/ }).getByTestId('graph-template-instantiate').click()

    const dialog = page.getByTestId('template-instantiate-dialog')

    await expect(dialog).toBeVisible()

    await dialog.locator('.el-form-item').filter({ hasText: '征集主题' }).locator('input').fill(THEME)
    await dialog.getByPlaceholder('例如：第 12 周选题会').fill(RUN_LABEL)
    const managerSelect = dialog.locator('.el-form-item').filter({ hasText: '负责人' }).locator('.el-select')
    await managerSelect.click()
    await page
      .locator('.el-select-dropdown:visible .el-select-dropdown__item')
      .filter({ hasText: 'demo.video.copy.lead@example.com' })
      .first()
      .click()
    await page.keyboard.press('Escape').catch(() => {})
    await dialog.getByText('部门全员').click()
    await expect(dialog.getByText(/将展开 \d+ 个采集任务/)).toBeVisible({ timeout: 15_000 })

    const runResp = page.waitForResponse(

      (r) => /\/workflow-graph\/templates\/.*\/runs\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),

      { timeout: 60_000 },

    )

    await page.getByTestId('template-instantiate-submit').click()

    await runResp

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

    await loginAs(page, ACCOUNTS.copyA, PASSWORD)

    await openCaptureTask(page, '提交选题')

    await submitCapture(page, `选题A ${RUN_TAG}`)

    await snap(page, 'phase-b-copy-a-capture.png')

    await logout(page)

    liveRow({ id: 'B1', phase: '采集 N1', actor: ACCOUNTS.copyA, result: 'PASS', note: '选题 A' })

  })



  test('Phase B2: copy.b submits capture', async ({ page }) => {

    await loginAs(page, ACCOUNTS.copyB, PASSWORD)

    await openCaptureTask(page, '提交选题')

    await submitCapture(page, `选题B ${RUN_TAG}`)

    await snap(page, 'phase-b-copy-b-capture.png')

    await logout(page)

    liveRow({ id: 'B2', phase: '采集 N1', actor: ACCOUNTS.copyB, result: 'PASS', note: '选题 B' })

  })



  test('Phase B3: copy.c submits capture', async ({ page }) => {

    await loginAs(page, ACCOUNTS.copyC, PASSWORD)

    await openCaptureTask(page, '提交选题')

    await submitCapture(page, `选题C ${RUN_TAG}`)

    await snap(page, 'phase-b-copy-c-capture.png')

    await logout(page)

    liveRow({ id: 'B3', phase: '采集 N1', actor: ACCOUNTS.copyC, result: 'PASS', note: '选题 C' })

  })



  test('Phase C-D: copy lead aggregate and batch dashboard', async ({ page }) => {

    await loginAs(page, ACCOUNTS.copyLead, PASSWORD)

    await openTaskCenter(page, 'tracking')

    const aggregateRow = page.getByTestId(listPanelTestId('tracking')).getByText('汇总派发').first()

    await expect(aggregateRow).toBeVisible({ timeout: 30_000 })

    await aggregateRow.click()

    await expect(page.getByTestId('template-aggregate-panel')).toBeVisible()

    await page.getByRole('button', { name: '刷新汇总' }).click()

    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(3, {

      timeout: 30_000,

    })

    await snap(page, 'phase-c-aggregate-matrix.png')

    const finalizeResp = page.waitForResponse(

      (r) => /\/finalize-topics\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),

      { timeout: 60_000 },

    )

    await page.getByTestId('template-aggregate-submit').click()

    await finalizeResp

    await snap(page, 'phase-c-finalize.png')



    await openTaskCenter(page, 'tracking')

    const rootRow = page.getByTestId(listPanelTestId('tracking')).getByText(RUN_LABEL).first()

    await expect(rootRow).toBeVisible({ timeout: 30_000 })

    await rootRow.click()

    await page.reload()

    await expect(page.getByTestId('video-tracking-panel')).toBeVisible({ timeout: 30_000 })
    expect(videoMockState.childRootTaskIds.length).toBe(3)
    await page.goto(`/task-center?filter=stats&selected=${videoMockState.rootTaskId}`)
    await expect(page.getByTestId('task-center-stats-view')).toBeVisible()

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
    await loginAs(page, ACCOUNTS.copyA, PASSWORD)
    const scriptTaskId = videoMockState.productionTasks[0]?.scriptTaskId ?? 'task-n3-1'
    await page.goto(`/task-center?filter=inbox&selected=${scriptTaskId}`)
    await expect(page.getByTestId('video-production-panel')).toBeVisible({ timeout: 30_000 })

    const acceptBtn = page.getByRole('button', { name: '接受任务' })
    if (await acceptBtn.isVisible().catch(() => false)) {
      await acceptBtn.click()
    }
    const startBtn = page.getByRole('button', { name: '开始处理' })
    if (await startBtn.isVisible().catch(() => false)) {
      await startBtn.click()
    }

    await page.getByTestId('video-production-note').fill(`脚本正文 ${RUN_TAG}`)
    const fileInput = page.locator('[data-testid="video-production-upload"] input[type="file"]')
    await fileInput.setInputFiles('e2e/fixtures/minimal.png')

    const deliverResp = page.waitForResponse(
      (r) => /\/api\/v1\/tasks\/.*\/deliverable\b/.test(r.url()) && r.request().method() === 'POST' && r.ok(),
      { timeout: 60_000 },
    )
    await page.getByTestId('video-production-submit').click()
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
    await loginAs(page, ACCOUNTS.copyLead, PASSWORD)
    const reviewTaskId = videoMockState.productionTasks[0]?.reviewTaskId ?? 'task-n4-1'
    const reviewOk = await page.evaluate(
      async ({ taskId, comment }) => {
        const res = await fetch(`/api/v1/tasks/${taskId}/review`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'approve', comment, quality_score: 5 }),
        })
        return res.ok
      },
      { taskId: reviewTaskId, comment: `审核通过 ${RUN_TAG}` },
    )
    expect(reviewOk).toBeTruthy()
    await page.goto(`/task-center?filter=inbox&selected=${reviewTaskId}`)
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


