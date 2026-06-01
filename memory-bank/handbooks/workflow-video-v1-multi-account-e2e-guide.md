# 视频制作全流程 · 多账号端到端测试指南

本指南描述用 **不同 demo 账号** 走完「选题会批次 → 按题 fork 制作子流 → 至少一条子流脚本撰写与审核（N3–N4）」的协同测试。支持 **Mock（无 Docker）** 与 **Live（真实 Docker 栈 + 种子）** 两种模式，阶段 A–F 均已自动化。

| 关联文档 | 用途 |
| --- | --- |
| [workflow-video-v1-collaborative-uat-guide.md](./workflow-video-v1-collaborative-uat-guide.md) | W0–W10 单账号功能 UAT（不替代本指南） |
| [workflow-video-v1-docker-runbook.md](./workflow-video-v1-docker-runbook.md) | 8080 开发栈种子与 API 冒烟 |
| [workflow-video-v1-implementation-plan.md](../plans/workflow-video-v1-implementation-plan.md) | 阶段定义与 pytest 基线 |

**自动化脚本**

| 模式 | Spec |
| --- | --- |
| Live | `frontend/e2e/live/workflow-video-multi-account-live.spec.ts` |
| Mock | `frontend/e2e/workflow-video-uat/workflow-video-multi-account-mock.spec.ts` |

---

## 0. 快速开始

### 无 Docker（推荐本地先跑）

```bash
cd frontend
npx playwright install chromium
npm run test:e2e:workflow-video-multi-account-mock
```

- **7 用例**，约 **2 分钟**（A–F 串行，4 个账号切换）。
- 密码：`secret-password`（mock 登录，非种子）。
- 报告目录：`verification-runs/workflow-video-live-<时间戳>/`（报告中标注 **Mock**）。

### 有 Docker Desktop（发版前）

```bash
cd frontend
npx playwright install chromium
npm run test:e2e:workflow-video-live
```

- **globalSetup** 约 **15–20 分钟**（重建 Compose 栈、种子、frontend/nginx）。
- **7 用例**约 **2–3 分钟**（不含 setup）。
- 基址：`http://127.0.0.1:38080`；种子密码：`FilumPlaywright123!`。
- **globalTeardown** 会 `docker compose down -v` 销毁 Live 栈。

### 与其他 E2E 套件的关系

| 命令 | 账号 | 范围 |
| --- | --- | --- |
| `npm run test:e2e:workflow-video` | admin | W10 冒烟 2 用例 |
| `npm run test:e2e:workflow-video-uat` | admin | W0–W10 单账号 UAT + 截图 |
| `npm run test:e2e:workflow-video-multi-account-mock` | copy lead/a/b/c | **本指南 A–F** |
| `npm run test:e2e:workflow-video-live` | copy lead/a/b/c | **本指南 A–F（真实栈）** |

---

## 1. 目标与范围

| 阶段 | 业务 | 参与账号 | 自动化 |
| --- | --- | --- | --- |
| A | 图模板实例化批次 Run | 文案负责人 `demo.video.copy.lead@example.com` | 是 |
| B | 三人提交选题（N1 采集） | 文案 `demo.video.copy.a/b/c@example.com` | 是 |
| C | 汇总派发（N2 finalize） | 文案负责人 | 是 |
| D | 批次看板验证 fork | 文案负责人 | 是 |
| E | 子流撰写脚本（N3） | 脚本撰写人（汇总指定，默认 `copy.a` 写题 A） | 是 |
| F | 脚本审核（N4） | 文案负责人（部门经理） | 是 |
| G | 配音 N5–N6 … 结案 N12 | 配音/后期等 | **人工**（见 §6） |

---

## 2. 环境准备

### 2.1 Mock 多账号（无 Docker）

见 §0。脚本通过 Playwright 路由 mock（`frontend/e2e/workflow-video-mock.ts`）模拟 API，**不替代** 后端 pytest 与 Docker 联调。

### 2.2 Live 一键栈（Playwright 专用）

`npm run test:e2e:workflow-video-live` 使用独立 Compose 项目 **`filum-playwright-live`**，与日常 8080 开发栈 **端口隔离**：

| 服务 | 端口 |
| --- | --- |
| HTTP（Nginx） | **38080** |
| Backend | 38000 |
| Frontend | 35173 |
| PostgreSQL | 35432 |
| Redis | 36379 |

`globalSetup`（[`frontend/e2e/live/global-setup.mjs`](../../frontend/e2e/live/global-setup.mjs)）流程：

1. `docker compose down -v` → 起 postgres/redis/backend（`--build`）
2. `seed_sample_data --password FilumPlaywright123!`
3. `seed_workflow_video_templates`
4. 起 frontend/nginx/worker；等待 `/login` 可访问

Compose 已设置 `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true`。配置见 [`frontend/e2e/live/compose-env.mjs`](../../frontend/e2e/live/compose-env.mjs)。

环境变量（可选覆盖）：

```bash
set PLAYWRIGHT_LIVE_BASE_URL=http://127.0.0.1:38080
set PLAYWRIGHT_LIVE_PASSWORD=FilumPlaywright123!
```

### 2.3 已有 Docker 开发栈（8080）

若已按 [workflow-video-v1-docker-runbook.md](./workflow-video-v1-docker-runbook.md) 启动 **8080** 栈：

1. `seed_sample_data` / `seed_workflow_video_templates` 已执行。
2. `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true` 并重启 backend。
3. 执行：

```bash
cd frontend
set PLAYWRIGHT_LIVE_BASE_URL=http://127.0.0.1:8080
set PLAYWRIGHT_LIVE_PASSWORD=FilumTest123!
npx playwright test -c playwright.workflow-video-live.config.ts
```

> 8080 栈 **不会** 被 Live spec 的 globalSetup 自动管理；需自行保证种子与开关一致。

---

## 3. 账号与职责

| 邮箱 | 姓名（种子） | 部门 | 本指南职责 |
| --- | --- | --- | --- |
| `demo.video.copy.lead@example.com` | 韩策 | 视频文案部 | 发布批次、汇总派发、看板、脚本审核 |
| `demo.video.copy.a@example.com` | 陆言 | 视频文案部 | 选题 A 采集；题 A 脚本撰写人（默认） |
| `demo.video.copy.b@example.com` | 宋遥 | 视频文案部 | 选题 B 采集 |
| `demo.video.copy.c@example.com` | 程野 | 视频文案部 | 选题 C 采集 |
| `demo.video.vo.a@example.com` | 白屿 | 视频配音部 | 人工：配音制作 N5 |
| `demo.video.post.lead@example.com` | 季衡 | 视频后期部 | 人工：指派剪辑 N7 |
| `demo.video.editor@example.com` | 叶舟 | 视频后期部 | 人工：剪辑/上传 N8–N10 |

---

## 4. 手工步骤（与自动化对齐）

> **任务中心导航要点**：URL 参数 `?selected=<task_id>` 仅在任务 **已出现在当前列表** 时生效（`TaskCenterView.effectiveSelectedTaskId`）。手工与自动化均建议：**打开对应筛选 Tab → 点击列表行** 打开详情；批次看板在选中 ROOT 后 **刷新页面** 更稳定。

### 阶段 A — 文案负责人：发起批次

1. 登录 → **任务模板** → **图模板** Tab。
2. 「选题会（批次）」→ **实例化**。
3. 填写：征集主题（含本次 Run 标记）、运行标题、负责人（本人 UUID 或经理）。
4. 参与人：自动化选 **指定成员** `copy.a` / `copy.b` / `copy.c`（**勿选部门全员**——全员含 lead 本人，若 lead 未完成 N1 采集则 N2 不会激活）。
5. 确认提示「将展开 3 个采集任务」→ **创建运行**。

> 参与人下拉数据来自 `POST .../preview-participants`，非 `GET /users`（copy lead 无 listUsers 权限时全员下拉会为空）。

### 阶段 B — 三名文案：提交选题

各用 **自己的账号** 登录（勿共用浏览器会话）：

1. **任务中心** → **待处理**。
2. 打开标题含「提交选题」的任务（点击列表行）。
3. **表格采集** 填写选题标题（建议 `选题A/B/C <Run标记>`）→ **提交**。

### 阶段 C — 文案负责人：汇总

1. **待处理** 或 **任务跟踪** 打开「汇总派发」（点击列表行）。
2. **刷新汇总**，确认 **3 行** 矩阵；每题 **脚本撰写人** 默认等于提交人（可改）。
3. **确认派发**（finalize-topics）。

**API 期望**：`child_instance_ids.length === 3`，`fork_status` 为 `completed` 或 `partial`。

### 阶段 D — 批次看板

1. finalize 后批次实例 **已完成**，ROOT 任务通常在 **历史**（偶发仍在 **跟踪**）。
2. **任务中心** → **历史**（或跟踪）→ 点击标题含 **运行标题**（如 `批次 <Run标记>`）的行。
3. **刷新页面** → 确认 **批次制作看板**（`batch-run-dashboard`）子 Run **3 行**。
4. 查看 **运行事件** 时间线（实例化、采集、汇总、fork）。

### 阶段 E — 脚本撰写人：N3

任务中心 **不** 单独列出「撰写脚本」节点标题，而是 **制作 Run 根任务**：

- 标题形如：`单题视频制作 / 选题A <Run标记>`
- 按 **选题标题**（如 `选题A …`）在 **待处理** 中定位，**点击列表行** 打开。

步骤：

1. 脚本撰写人（题 A 默认 `copy.a`）登录 → **待处理** → 打开题 A 制作 Run。
2. 若有 **接受任务** / **开始处理**，先点击。
3. 在 **交付与验收** 区填写 **交付说明** → **提交交付物**。

> N3 未配置 `capture_schema`，**无** 表格采集面板，走任务中心交付/验收流。

### 阶段 F — 文案负责人：N4 审核

1. 负责人登录 → **待处理**（或跟踪）→ 打开 **同一题 A 制作 Run**（E 提交后 status=review）。
2. 点击 **验收通过**（可填验收评价）。

---

## 5. 通过标准

- 三人采集后，负责人汇总矩阵 **3 行**。
- finalize 响应：`child_instance_ids` **3 条**，`fork_status` ∈ `{completed, partial}`。
- 看板子 Run 行数 **= 通过题数（3）**。
- 脚本撰写人可在题 A 制作 Run 上 **提交交付物**。
- 负责人可对同一制作 Run **验收通过**；子流事件时间线推进至 N4 之后。

---

## 6. 完整制作链（N5–N12）人工延伸

自动化止于 N4（避免单次超过 30 分钟）。后续按种子模板顺序人工走查：

1. **白屿** `demo.video.vo.a`：N5 配音（握手接受 → 交付）。
2. **韩策**：N6 配音审核。
3. **季衡** `demo.video.post.lead`：N7 指派剪辑（表格采集剪辑人 → 选 **叶舟**）。
4. **叶舟** `demo.video.editor`：N8 剪辑 → N10 上传。
5. **季衡 / 韩策**：N9 成片审核、N11 排期、N12 结案。

每步在 **待处理 / 任务跟踪** 按任务标题与 `template_node_key` 区分。

---

## 7. 自动化命令与产物

| 模式 | 命令 | 配置 |
| --- | --- | --- |
| Live（Docker + 种子） | `npm run test:e2e:workflow-video-live` | `playwright.workflow-video-live.config.ts` |
| Mock 多账号（无 Docker） | `npm run test:e2e:workflow-video-multi-account-mock` | `playwright.workflow-video-multi-account-mock.config.ts` |

| 产物 | 路径 |
| --- | --- |
| Markdown 报告 | `verification-runs/workflow-video-live-*/report.md` |
| 截图 | `verification-runs/workflow-video-live-*/screenshots/` |
| Playwright HTML | `verification-runs/workflow-video-live-*/playwright-html/` |
| JSON 结果 | `verification-runs/workflow-video-live-*/results.json` |

查看 HTML 报告：

```bash
npx playwright show-report verification-runs/workflow-video-live-<时间戳>/playwright-html
```

---

## 8. 故障排查

| 现象 | 原因 / 处理 |
| --- | --- |
| 图模板 Tab 无实例化 / 403 | `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true` |
| 参与人下拉为空 | 应用 `preview-participants` 填充选项；勿依赖 `listUsers` |
| 实例化后 copy 成员 inbox=0 | 图实例化未 `commit`；确认 `WorkflowVideoInstantiationService` 已持久化 |
| 汇总矩阵为空 | B 阶段三人均已提交；点「刷新汇总」 |
| finalize 409 `assignee_role: member` | `workflow_rule_resolver` 需支持 `member`（单数） |
| finalize 409 缺少 `edit_assignee_id` | 生产 fork 仅对 **start** 节点解析 assignee |
| `batch-run-dashboard` 不可见 | finalize 后 ROOT 在 **历史**；须 **点击运行标题行 → reload**；勿仅用 URL `selected=` |
| 脚本撰写人找不到「撰写脚本」 | 任务中心显示 **制作 Run 根任务**（`单题视频制作 / 选题A …`），按 **选题标题** 搜，非节点名 |
| 负责人找不到「脚本审核」 | 同上，打开 **题 A 制作 Run**（review 态），按钮为 **验收通过** |
| 看板 0 子 Run | finalize 失败或未 fork；查 `GET .../instances/{batch_id}/children` |
| 登录 429 | 提高 `AUTH_LOGIN_RATE_LIMIT` 或串行退避（Live 栈默认 120/min） |

---

## 9. 验收记录（report.md）

`test.afterAll` 调用 [`frontend/e2e/live/workflow-video-live-report.ts`](../../frontend/e2e/live/workflow-video-live-report.ts) 生成报告，字段示例：

| 列 | 含义 |
| --- | --- |
| 步骤 ID | A1、B1…F1 |
| 阶段 | 批次实例化、采集 N1、汇总派发… |
| 账号 | 执行该步的 demo 邮箱 |
| 结果 | PASS / FAIL |
| 说明 | Run 标记、题数等 |

报告头部含 **执行模式**（Live / Mock）、Run 标记、基址、输出目录与时间戳。

---

**修订约定**：变更种子账号、模板节点、任务中心 UI 或 spec 导航逻辑时，同步更新本文件与 `workflow-video-multi-account-live.spec.ts` / `workflow-video-multi-account-mock.spec.ts`。
