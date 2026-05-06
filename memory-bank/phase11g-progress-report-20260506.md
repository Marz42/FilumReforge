# Phase 11-G 进展报告（2026-05-06）

## 1. 结论摘要

- 工作流重构 Phase 11-A 至 11-G 当前已全部完成，其中 11-G 已完成文档收口、前端可测性加固、Playwright mock/live 双轨浏览器基线与前端回归验证。
- 当前项目主线不再停留在“补齐 Playwright 基线”，而是回到部署工程化收口、Linux/Ubuntu 近似环境发布演练，以及更大范围真实业务 E2E 扩面。
- 本轮未触碰现有两处 backend 脏改动；live 场景通过独立 Compose project + 隔离端口执行，避免与用户本地环境直接冲突。

## 2. 本轮新增交付

- 前端测试基础设施：新增 `frontend/playwright.live.config.ts`、`frontend/e2e/live/compose-env.mjs`、`frontend/e2e/live/docker-compose.playwright-live.yml`、`frontend/e2e/live/task-center-live.spec.ts`，并在 `frontend/package.json` 增补 `test:e2e:live` / `test:e2e:live:headed`。
- 可测性锚点：`frontend/src/views/LoginView.vue`、`frontend/src/views/TaskCenterView.vue`、`frontend/src/views/TasksView.vue` 新增稳定 `data-testid`；任务中心发布抽屉补齐标题、说明、执行人、部门、优先级、提交按钮等锚点。
- 单测与文档：`frontend/tests/LoginView.spec.ts`、`frontend/tests/TaskCenterView.spec.ts` 已补 selector 覆盖；`frontend/README.md` 已新增 mock/live 两套 Playwright 运行说明。

## 3. 验证结果

已完成验证命令：

```powershell
cd frontend
npm run test:unit -- --run
npm run type-check
npm run build
npm run test:e2e
npm run test:e2e:live
```

验证结论：

- Vitest：19 files / 76 tests passed
- mock Playwright：4 passed
- live Playwright：1 passed（真实 backend + sample data + 任务创建）
- type-check：通过
- build：通过

## 4. 当前项目进度判断

- 已完成：Phase A-5、重构 Step 1-7、工作流重构 Phase 0-11-G。
- 仍在进行：工作流 E 后续深化、部署工程化收口、Linux/Ubuntu 近似环境发布演练。
- 尚未完成但已明确：公开注册/审批式注册、更大范围 lifecycle 规则化联动、真实 Email/WebSocket 渠道深化、更大覆盖面的业务 E2E。

## 5. 证据文件

- `frontend/playwright.config.ts`
- `frontend/playwright.live.config.ts`
- `frontend/e2e/fixtures.ts`
- `frontend/e2e/live/compose-env.mjs`
- `frontend/e2e/live/task-center-live.spec.ts`
- `frontend/src/views/LoginView.vue`
- `frontend/src/views/TaskCenterView.vue`
- `frontend/src/views/TasksView.vue`
- `frontend/tests/LoginView.spec.ts`
- `frontend/tests/TaskCenterView.spec.ts`
- `memory-bank/workflow-refactor-implementation-plan.md`
- `memory-bank/progress.md`

## 6. 后续建议顺序

1. 在 Linux/Ubuntu 近似环境执行 `bash scripts/check-release.sh` 与实际发布/回滚演练，补齐部署工程化闭环。
2. 以现有 Playwright live 基线为起点，扩到消息中心、模板入口、邀请注册等真实业务流，而不是继续只做 mock API 覆盖。
3. 等生产近似演练稳定后，再评估是否把 Playwright 纳入默认发布闸门，以及是否收缩 `TASK_CENTER_V2_ENABLED` 的回退窗口。