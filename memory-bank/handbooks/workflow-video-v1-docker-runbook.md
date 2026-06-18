# 视频工作流 v1 — Docker 本地复现 Runbook（W6）

## 前置

- Docker Compose 栈已启动（PostgreSQL + API + 前端按项目惯例）。
- 数据库迁移已执行：`alembic upgrade head`（在 API 容器或 backend 目录）。

## 1. 组织与账号种子

```bash
docker compose exec backend python -m app.scripts.seed_sample_data --password FilumTest123!
```

将创建：

- 视频相关部门：`video-copywriting`、`video-voice`、`video-post`（含 `publish_org_task` 能力）
- Demo 账号：`demo.video.copy.lead@example.com`、`demo.video.copy.a/b/c@example.com`、`demo.video.vo.lead@example.com`、`demo.video.vo.a@example.com`、`demo.video.post.lead@example.com`、`demo.video.editor@example.com`
- 图模板（用户可见「任务模板」）：`topic_meeting_batch_v1`、`video_production_per_topic_v1`（N1–N2 / N3–N12 + 打回边）

仅重跑图模板（组织已存在时；`launch_schema` / `seed_version` 变更后也必须重跑以刷新实例化表单）：

```bash
docker compose exec backend python -m app.scripts.seed_workflow_video_templates
```

**生产机部门 code 不是 demo 三件套时**（常见：多个文案部 + 一个后期部），指定现有部门编码：

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.seed_workflow_video_templates \
  --copy-dept-code <主文案部code> \
  --post-dept-code <后期部code>
```

`--voice-dept-code` 可省略（新版 N5 已合并配音上传，配音池仅为配置占位，默认与文案部相同）。

## 2. 功能开关（W9）

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/workflow-graph/feature-flags
```

关键项：`workflow_graph_template_engine_enabled` 须为 `true` 才能实例化任务模板。

## 3. 启用图模板引擎（任务模板实例化依赖）

在 API 环境变量中设置（`.env` 或 Compose）：

```text
WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true
```

[`infra/docker/docker-compose.yml`](../../infra/docker/docker-compose.yml) 已透传该变量（默认 `${WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED:-false}`）；本地开发栈请在 `infra/docker/.env` 设为 `true` 并重启 API 容器。

重启 API 容器使配置生效。

## 4. 冒烟检查（API）

以具备 `can_publish_org_tasks` 的账号登录（如 `demo.video.copy.lead@example.com` 或部门负责人）。

1. `GET /workflow-graph/templates` — 应看到 `topic_meeting_batch_v1`、`video_production_per_topic_v1` 且 `status=active`。
2. `POST /workflow-graph/templates/{batch_id}/runs` — body 含 `theme`、`manager_user_id`（**UUID**，来自实例化 Dialog 负责人下拉或 `GET .../managed-department-member-options`）、`participants_snapshot.copywriters`。
3. 文案账号提交 N1 采集 → N2 汇总 `finalize-topics` → 自动 fork 子 Run。
4. `POST /workflow-graph/instances/{batch_id}/fork-production` — 幂等，重复调用不重复子 Run。

## 5. 运行事件（W8）

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/workflow-graph/instances/{instance_id}/events?limit=20&offset=0"
```

任务详情与批次 ROOT 看板会展示同一时间线数据。

## 6. 测试命令（开发机）

```bash
cd backend
pytest -q tests/test_workflow_video_w6_template_seed.py
```

全量视频回归（可选）：

```bash
pytest -q tests/test_workflow_video_w0_baseline.py tests/test_workflow_video_w1_contracts.py tests/test_workflow_video_w2_participant_resolution.py tests/test_workflow_video_wf_form_engine.py tests/test_workflow_video_w3_instantiation.py tests/test_workflow_video_w4_orchestration.py tests/test_workflow_video_w5_rework.py tests/test_workflow_video_wfk_fork.py tests/test_workflow_video_w6_template_seed.py tests/test_workflow_video_w8_events.py tests/test_workflow_video_w9_closure.py tests/test_workflow_video_w10_regression.py
```

## 7. 前端 E2E（W10 / W0–W10 UAT，mock API）

**全阶段协同 UAT（截图 + `report.md`）**：见 [workflow-video-v1-collaborative-uat-guide.md](./workflow-video-v1-collaborative-uat-guide.md)，命令 `npm run test:e2e:workflow-video-uat`。

**W10 冒烟（两条用例）**：

开发机需已安装 Playwright 浏览器：`npx playwright install chromium`。

```bash
cd frontend
npm run test:e2e:workflow-video
# 等价：npx playwright test e2e/workflow-video-v1.spec.ts
```

用例覆盖：任务模板页实例化 → 三次采集 → 汇总 finalize → 批次看板 3 子 Run + 子流制作详情；仅 2 次采集并汇总时看板 2 行。

## 8. Playwright Live 多账号 E2E（A–F）

与 §1–§7 的 **8080 开发栈** 不同，Live E2E 使用独立 Compose 项目 **`filum-playwright-live`**，HTTP 端口 **38080**，密码 **`FilumPlaywright123!`**（见 `frontend/e2e/live/compose-env.mjs`）。

```bash
cd frontend
npx playwright install chromium
npm run test:e2e:workflow-video-live
```

- `globalSetup` 重建栈、`seed_sample_data`、`seed_workflow_video_templates`；`globalTeardown` 销毁栈。
- 7 用例（copy lead + copy.a/b/c，阶段 A–F）；产物 `verification-runs/workflow-video-live-*/`。
- 无 Docker 时先跑 Mock：`npm run test:e2e:workflow-video-multi-account-mock`。

完整步骤、手工对齐与故障排查见 [workflow-video-v1-multi-account-e2e-guide.md](./workflow-video-v1-multi-account-e2e-guide.md)。
