# 视频工作流 v1 协同测试指南（W0–W10）

本指南供**产品、测试、后端、前端**在版本收口或发版前协同验收，并与自动化脚本共用同一检查表。

| 关联文档 | 用途 |
| --- | --- |
| [workflow-video-v1-implementation-plan.md](../plans/workflow-video-v1-implementation-plan.md) | 阶段定义与必绿 pytest |
| [workflow-video-v1-docker-runbook.md](./workflow-video-v1-docker-runbook.md) | Docker + 真实种子数据联调 |
| [e2e-gui-verification-automation-runbook.md](./e2e-gui-verification-automation-runbook.md) | 全站 Docker GUI 验证（非视频专用） |
| [workflow-video-v1-multi-account-e2e-guide.md](./workflow-video-v1-multi-account-e2e-guide.md) | 多账号 A–F Live/Mock E2E（跨账号协同，非 W0–W10 单账号 UAT） |

---

## 1. 协同角色与分工

| 角色 | 负责 | 交付物 |
| --- | --- | --- |
| 产品 | 口径确认、批次/子 Run 是否易混淆 | 签字检查表 §3 |
| 测试 | 执行本指南 + Playwright UAT；整理 `report.md` | 截图目录 + 缺陷单 |
| 后端 | `pytest` 全绿；Docker 种子；API 契约 | CI 日志 / Runbook 复现步骤 |
| 前端 | `vitest` + `type-check`；mock/live E2E | PR 内测试命令输出 |

**协同节奏建议**：每日站会过「阻塞项」；阶段收口时跑 **§4 自动化一键** + **§5 人工补测**。

---

## 2. 环境与模式

### 2.1 Mock UAT（默认，无需 Docker）

- 前端 Vite `127.0.0.1:4173` + Playwright 路由 mock（`frontend/e2e/workflow-video-mock.ts`）。
- 覆盖 **UI 交互与主路径**；W5 打回通过 API 注入 + 时间线断言（汇总表尚无打回按钮）。
- **不替代** 后端集成测试与真实人事/部门数据。

### 2.2 Docker Live（发版前建议）

- 按 [workflow-video-v1-docker-runbook.md](./workflow-video-v1-docker-runbook.md) 启动 **8080** 栈并 `seed_workflow_video_templates`。
- 设置 `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true`。
- **多账号 A–F 自动化**：`npm run test:e2e:workflow-video-live`（Playwright 专用 `:38080` 栈，见 [multi-account E2E 指南](./workflow-video-v1-multi-account-e2e-guide.md)）；或对接已有 8080 栈并设置 `PLAYWRIGHT_LIVE_BASE_URL` / `PLAYWRIGHT_LIVE_PASSWORD`。
- 人工走查 §5（权限/打回/通知等 mock 未覆盖项；制作链 happy path 已由 Mock A–N 覆盖）。

### 2.3 仅后端契约（开发自测）

```bash
cd backend
pytest -q tests/test_workflow_video_w0_baseline.py tests/test_workflow_video_w1_contracts.py \
  tests/test_workflow_video_w2_participant_resolution.py tests/test_workflow_video_wf_form_engine.py \
  tests/test_workflow_video_w3_instantiation.py tests/test_workflow_video_w4_orchestration.py \
  tests/test_workflow_video_w5_rework.py tests/test_workflow_video_wfk_fork.py \
  tests/test_workflow_video_w6_template_seed.py tests/test_workflow_video_w8_events.py \
  tests/test_workflow_video_w9_closure.py tests/test_workflow_video_w10_regression.py
```

---

## 3. W0–W10 功能检查表

| 阶段 | 验收要点 | 自动化（Playwright UAT） | 人工补测 |
| --- | --- | --- | --- |
| **W0** | 任务模板单入口（图模板列表 + 实例化） | W0-1 截图 | Legacy E UI 已移除 @ `0.89.0` |
| **W1** | `instance_key`、批次/子关联、`launch_schema` 字段 | W1-1 征集主题/负责人 | 迁移 `alembic upgrade head` |
| **W2** | `preview-participants`、snapshot 不受事后改人影响 | W2-1 展开 N 人提示 | 改部门成员后重实例化对比 |
| **WF** | 采集行表、submissions、finalize 写 context | WF-1 三次采集 + 矩阵 | API 非法 schema 422 |
| **W3** | `POST .../templates/{id}/runs`、3×N1 待办 | W3-1 创建运行 | ROOT 任务标题前缀 |
| **W4** | 采集齐后 N2 激活 | W4-1 N2 面板 | 第三人提交前 N2 不可见 |
| **W5** | 题级打回仅重开对应采集 | W5-1 API + 时间线 | 小张一题打回（Docker） |
| **WFK** | finalize 按题 fork 子 Run | WFK-1 看板 3 行 | 幂等重复 finalize |
| **W6** | 双模板种子编码 | W6-1 列表两模板 | Runbook 种子脚本 |
| **W7** | Dialog / Capture / Aggregate / 看板 | W7-1 全流程截图 | 移动端窄屏 |
| **W8** | `workflow_run_events` 时间线 | W8-1 多事件类型 | 分页 limit/offset |
| **W9** | Outbox、模板 GET/PATCH（后端 pytest） | W9-1 单入口文案 | feature-flags API |
| **W10** | 回归 + 文档基线 | W10-1 两题 fork | 全量 pytest 53+ |

---

## 4. Playwright 自动化 UAT（截图 + 报告）

### 4.1 前置

```bash
cd frontend
npm ci   # 或 npm install
npx playwright install chromium
```

### 4.2 执行

```bash
cd frontend
npm run test:e2e:workflow-video-uat
```

### 4.3 产出物

| 路径 | 内容 |
| --- | --- |
| `verification-runs/workflow-video-uat-<时间戳>/screenshots/` | 按阶段命名的全页 PNG（`w00-*.png` … `w10-*.png`） |
| `verification-runs/workflow-video-uat-<时间戳>/report.md` | 步骤 ID / 阶段 / PASS/FAIL 汇总表 + 截图索引 |
| `verification-runs/workflow-video-uat-<时间戳>/playwright-html/` | Playwright HTML 报告（含 trace/失败录像） |
| `verification-runs/workflow-video-uat-<时间戳>/results.json` | 机器可读结果 |

查看 HTML 报告：

```bash
cd frontend
npx playwright show-report verification-runs/workflow-video-uat-<时间戳>/playwright-html
```

### 4.4 与冒烟套件关系

| 命令 | 范围 |
| --- | --- |
| `npm run test:e2e:workflow-video` | W10 两条快速 mock 冒烟 |
| `npm run test:e2e:workflow-video-uat` | **本指南 W0–W10 全阶段** + 截图 + `report.md` |
| `npm run test:e2e:workflow-video-multi-account-mock` | 多账号 A–N（mock，**15 用例**，N1–N12） |
| `npm run test:e2e:workflow-video-live` | 多账号 A–F（Docker Live 栈，7 用例） |

---

## 5. 人工补测清单（mock 无法覆盖）

1. **权限**：非 admin 发布组织任务、部门外用户不可实例化。
2. **并发**：两人同时 finalize 同一批次（幂等与锁）。
3. **制作链打回/deep_reject**：Mock A–N 覆盖 happy path；打回边仍建议 Docker 种子 + 多账号 **人工**抽测（见 [multi-account E2E 指南 §6](./workflow-video-v1-multi-account-e2e-guide.md)）。
4. **消息/通知**：W9 outbox `workflow_node_activated` 下游投递（查 outbox 表或集成环境）。
5. **性能**：汇总矩阵 30 人 × 100 题滚动与提交耗时。
6. **回归**：发版前跑 §2.3 全量 pytest + `npm run type-check`。

---

## 6. 缺陷记录模板

```markdown
### [VIDEO-xxx] 标题
- **阶段**：W7
- **环境**：mock UAT / Docker 8080
- **步骤**：…
- **期望**：…
- **实际**：…
- **截图**：verification-runs/.../screenshots/w07-01-....png
- **日志**：pytest / 浏览器 Network
```

---

## 7. 发版签字（可选）

| 检查项 | 负责人 | 日期 | 签字 |
| --- | --- | --- | --- |
| §4 UAT `report.md` 全 PASS | 测试 | | |
| §2.3 pytest 全绿 | 后端 | | |
| Docker Runbook 冒烟 | 运维/测试 | | |
| 产品口径 §3 无遗留 P0 | 产品 | | |

---

**修订**：新增 Playwright 套件或阶段变更时，同步更新 `frontend/e2e/workflow-video-uat/workflow-video-w0-w10-uat.spec.ts` 与本文件 §3 表。
