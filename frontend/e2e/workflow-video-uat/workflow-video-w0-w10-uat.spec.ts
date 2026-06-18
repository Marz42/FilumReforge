/**
 * 视频工作流 v1：W0–W10 功能性协同 UAT（mock API + 全页截图 + report.md）
 *
 * 运行：cd frontend && npm run test:e2e:workflow-video-uat
 * 产出：verification-runs/workflow-video-uat-<时间戳>/{screenshots,report.md,playwright-html,results.json}
 */
import { expect, test, type Page } from '@playwright/test'

import { installWorkflowVideoMockApi, loginAsAdmin, videoMockState } from '../workflow-video-mock'
import { getUatShotDir, uatRow, uatShot, writeUatReport } from './uat-report'

test.describe.configure({ mode: 'serial' })

async function snap(page: Page, filename: string): Promise<void> {
  await page.screenshot({ path: uatShot(filename), fullPage: true })
}

async function openBatchInstantiateDialog(page: Page): Promise<void> {
  await page.goto('/task-templates')
  await page.getByRole('tab', { name: /图模板/ }).click()
  await page.getByRole('row', { name: /选题会（批次）/ }).getByTestId('graph-template-instantiate').click()
}

test.describe('Workflow Video v1 W0–W10 UAT', () => {
  test.beforeEach(async ({ page }) => {
    videoMockState.captureSubmitted.clear()
    videoMockState.finalized = false
    videoMockState.forked = false
    videoMockState.sessionActive = false
    videoMockState.rejectedTopicIds.clear()
    videoMockState.childInstanceIds = []
    videoMockState.childRootTaskIds = []
    await installWorkflowVideoMockApi(page)
    await loginAsAdmin(page)
  })

  test.afterAll(() => {
    writeUatReport([
      '## 说明',
      '',
      '- **W0/W1** 部分能力仅能通过契约与开关验证；本套件以 UI 可观测子集 + mock API 行为代替。',
      '- **W5 打回**：前端尚无汇总表打回按钮，UAT 通过 `reject-captures` API + 事件时间线验收。',
      '- **Live/Docker**：完整联调见 `memory-bank/handbooks/workflow-video-v1-docker-runbook.md`。',
    ])
  })

  test('W0 基线：Legacy 与图模板分栏', async ({ page }) => {
    await page.goto('/task-templates')
    await expect(page.getByTestId('task-templates-page')).toBeVisible()
    await expect(page.getByText('E · Legacy')).toBeVisible()
    await snap(page, 'w00-01-task-templates-legacy-tab.png')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await expect(page.getByTestId('task-templates-graph-tab')).toBeVisible()
    await snap(page, 'w00-02-task-templates-graph-tab.png')
    uatRow({
      id: 'W0-1',
      phase: 'W0 基线',
      result: 'PASS',
      note: '任务模板页 E·Legacy 与图模板 v1 Tab 分栏可见',
    })
  })

  test('W1/W2/W3：实例化 Dialog 与参与者预览', async ({ page }) => {
    await openBatchInstantiateDialog(page)
    const dialog = page.getByTestId('template-instantiate-dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText('征集主题')).toBeVisible()
    await expect(dialog.getByText('负责人')).toBeVisible()
    await snap(page, 'w01-w03-01-instantiate-launch-schema.png')
    await expect(page.getByText(/将展开 \d+ 个采集任务/)).toBeVisible({ timeout: 15_000 })
    await snap(page, 'w02-01-participant-preview.png')
    await dialog.locator('.el-form-item').filter({ hasText: '征集主题' }).locator('input').fill('UAT 协同测试')
    await dialog.getByText('部门全员').click()
    await page.getByTestId('template-instantiate-submit').click()
    uatRow({ id: 'W1-1', phase: 'W1 契约', result: 'PASS', note: 'launch_schema 字段渲染' })
    uatRow({ id: 'W2-1', phase: 'W2 参与者', result: 'PASS', note: 'preview-participants 展开人数提示' })
    uatRow({ id: 'W3-1', phase: 'W3 实例化', result: 'PASS', note: 'POST templates/.../runs 创建批次 Run' })
  })

  test('WF/W4：三次采集与 N2 汇总面板', async ({ page }) => {
    await openBatchInstantiateDialog(page)
    await page.getByTestId('template-instantiate-submit').click()

    for (const [index, taskId] of ['task-capture-a', 'task-capture-b', 'task-capture-c'].entries()) {
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await expect(page.getByTestId('template-capture-panel')).toBeVisible()
      await page.getByTestId('template-capture-title').fill(`UAT 选题 ${index + 1}`)
      const captureResponse = page.waitForResponse(
        (res) => res.url().includes('/submit-capture') && res.ok(),
      )
      await page.getByTestId('template-capture-submit').click()
      await captureResponse
      await snap(page, `w04-wf-0${index + 1}-capture-${taskId}.png`)
    }

    await page.goto('/task-center?filter=tracking&selected=task-n2-aggregate')
    await expect(page.getByTestId('template-aggregate-panel')).toBeVisible()
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(3)
    await snap(page, 'w04-wf-04-aggregate-matrix.png')
    uatRow({ id: 'WF-1', phase: 'WF 表单引擎', result: 'PASS', note: '三次 submit-capture + 汇总矩阵 3 行' })
    uatRow({ id: 'W4-1', phase: 'W4 编排', result: 'PASS', note: '采集完成后 N2 汇总面板可加载 submissions' })
  })

  test('W5：题级打回（API）+ 事件时间线', async ({ page }) => {
    await openBatchInstantiateDialog(page)
    await page.getByTestId('template-instantiate-submit').click()

    await page.goto('/task-center?filter=tracking&selected=task-capture-a')
    await page.getByTestId('template-capture-title').fill('UAT 打回题')
    const captureDone = page.waitForResponse((res) => res.url().includes('/submit-capture') && res.ok())
    await page.getByTestId('template-capture-submit').click()
    await captureDone

    const rejectOk = await page.evaluate(
      async ({ instanceId, topicId }) => {
        const res = await fetch(`/api/v1/workflow-graph/instances/${instanceId}/reject-captures`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_ids: [topicId], reason: 'UAT 定向打回' }),
        })
        return res.ok
      },
      { instanceId: videoMockState.batchInstanceId, topicId: videoMockState.topicIds[0] },
    )
    expect(rejectOk).toBeTruthy()

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('workflow-run-events-compact')).toBeVisible()
    await expect(page.getByTestId('workflow-run-events-compact').getByText('采集已打回')).toBeVisible()
    await snap(page, 'w05-01-capture-rejected-event.png')
    uatRow({
      id: 'W5-1',
      phase: 'W5 定向返工',
      result: 'PASS',
      note: 'reject-captures API；时间线展示 capture_rejected（UI 打回按钮待产品化）',
    })
  })

  test('WFK/W6/W7/W8：汇总派发、双模板、看板与时间线', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /图模板/ }).click()
    await expect(page.getByText('topic_meeting_batch_v1')).toBeVisible()
    await expect(page.getByText('video_production_per_topic_v1')).toBeVisible()
    await snap(page, 'w06-01-dual-templates-list.png')
    uatRow({ id: 'W6-1', phase: 'W6 双模板', result: 'PASS', note: '图模板库含批次 + 制作模板编码' })

    await page.getByRole('row', { name: /选题会（批次）/ }).getByTestId('graph-template-instantiate').click()
    await page.getByTestId('template-instantiate-submit').click()

    for (const taskId of ['task-capture-a', 'task-capture-b', 'task-capture-c']) {
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await page.getByTestId('template-capture-title').fill('UAT')
      await page.getByTestId('template-capture-submit').click()
    }

    await page.goto('/task-center?filter=tracking&selected=task-n2-aggregate')
    await page.getByRole('button', { name: '刷新汇总' }).click()
    const finalizeResponse = page.waitForResponse(
      (res) => res.url().includes('/finalize-topics') && res.ok(),
    )
    await page.getByTestId('template-aggregate-submit').click()
    await finalizeResponse
    await snap(page, 'w07-01-aggregate-finalize.png')

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('video-tracking-panel')).toBeVisible()
    expect(videoMockState.childRootTaskIds.length).toBe(3)
    await page.goto(`/task-center?filter=stats&selected=${videoMockState.rootTaskId}`)
    await expect(page.getByTestId('task-center-stats-view')).toBeVisible()
    await expect(page.getByTestId('task-center-stats-events')).toBeVisible()
    await snap(page, 'w08-wfk-01-batch-dashboard-and-events.png')

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.childRootTaskIds[0]}`)
    await expect(page.getByText('制作 Run')).toBeVisible()
    await snap(page, 'w07-02-child-production-run.png')

    uatRow({ id: 'WFK-1', phase: 'WFK fork', result: 'PASS', note: 'finalize 后看板 3 子 Run' })
    uatRow({ id: 'W7-1', phase: 'W7 前端', result: 'PASS', note: 'Capture/Aggregate/批次看板/子流详情' })
    uatRow({ id: 'W8-1', phase: 'W8 EventLog', result: 'PASS', note: 'batch-run-event-timeline 多事件类型' })
  })

  test('W9：收口（Legacy 提示文案）', async ({ page }) => {
    await page.goto('/task-templates')
    await page.getByRole('tab', { name: /任务模板/ }).click()
    await expect(page.getByText(/逐步迁移至「图模板」/)).toBeVisible()
    await snap(page, 'w09-01-legacy-hint.png')
    uatRow({
      id: 'W9-1',
      phase: 'W9 收口',
      result: 'PASS',
      note: 'E·Legacy Tab 与迁移提示；Outbox/模板 CRUD 见后端 pytest',
    })
  })

  test('W10：端到端回归（两题 fork）', async ({ page }) => {
    await openBatchInstantiateDialog(page)
    await page.getByTestId('template-instantiate-submit').click()

    for (const taskId of ['task-capture-a', 'task-capture-b']) {
      await page.goto(`/task-center?filter=tracking&selected=${taskId}`)
      await page.getByTestId('template-capture-title').fill('UAT')
      await page.getByTestId('template-capture-submit').click()
    }

    await page.goto('/task-center?filter=tracking&selected=task-n2-aggregate')
    await page.getByRole('button', { name: '刷新汇总' }).click()
    await expect(page.locator('[data-testid="template-aggregate-panel"] tbody tr')).toHaveCount(2)
    await page.getByTestId('template-aggregate-submit').click()

    await page.goto(`/task-center?filter=tracking&selected=${videoMockState.rootTaskId}`)
    await page.reload()
    await expect(page.getByTestId('video-tracking-panel')).toBeVisible()
    expect(videoMockState.childRootTaskIds.length).toBe(2)
    await snap(page, 'w10-01-two-child-fork.png')
    uatRow({
      id: 'W10-1',
      phase: 'W10 硬化',
      result: 'PASS',
      note: '两题采集 + 汇总派发 → 看板 2 子 Run（与 workflow-video-v1.spec 对齐）',
    })
  })
})
