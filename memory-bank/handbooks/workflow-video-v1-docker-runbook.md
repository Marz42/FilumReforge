# 视频工作流 v1 — Docker 本地复现 Runbook（W6）

## 前置

- Docker Compose 栈已启动（PostgreSQL + API + 前端按项目惯例）。
- 数据库迁移已执行：`alembic upgrade head`（在 API 容器或 backend 目录）。

## 1. 组织与账号种子

```bash
docker compose exec api python -m app.scripts.seed_sample_data --password FilumTest123!
```

将创建：

- 视频相关部门：`video-copywriting`、`video-voice`、`video-post`（含 `publish_org_task` 能力）
- Demo 账号：`demo.video.copy.lead@example.com`、`demo.video.copy.a/b/c@example.com`、`demo.video.vo.lead@example.com`、`demo.video.vo.a@example.com`、`demo.video.post.lead@example.com`、`demo.video.editor@example.com`
- 图模板：`topic_meeting_batch_v1`、`video_production_per_topic_v1`（N1–N2 / N3–N12 + 打回边）

仅重跑图模板（组织已存在时）：

```bash
docker compose exec api python -m app.scripts.seed_workflow_video_templates
```

## 2. 功能开关（W9）

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/workflow-graph/feature-flags
```

关键项：`workflow_graph_template_engine_enabled` 须为 `true` 才能实例化图模板。

## 3. 启用图模板引擎

在 API 环境变量中设置：

```text
WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true
```

重启 API 容器使配置生效。

## 4. 冒烟检查（API）

以具备 `can_publish_org_tasks` 的账号登录（如 `demo.video.copy.lead@example.com` 或部门负责人）。

1. `GET /workflow-graph/templates` — 应看到 `topic_meeting_batch_v1`、`video_production_per_topic_v1` 且 `status=active`。
2. `POST /workflow-graph/templates/{batch_id}/runs` — body 含 `theme`、`manager_user_id`（客户成功负责人 `demo.success@example.com` 亦可）、`participants_snapshot.copywriters`。
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
pytest -q tests/test_workflow_video_w0_policy.py tests/test_workflow_video_w1_participants.py tests/test_workflow_video_wf_form_engine.py tests/test_workflow_video_w3_instantiation.py tests/test_workflow_video_w4_orchestration.py tests/test_workflow_video_w5_rework.py tests/test_workflow_video_wfk_fork.py tests/test_workflow_video_w6_template_seed.py tests/test_workflow_video_w8_events.py
```
