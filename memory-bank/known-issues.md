# 已知问题与调试心得

> 🧊 COLD — Bug 排查或环境问题时读取。新坑位追加到文末。

---

## 环境与工具链

### Windows 下 `check-release.sh` 失败

**现象**: Git Bash/WSL 直跑 `scripts/check-release.sh` 因 `node_modules` 跨平台绑定或 PATH 无 `python` 失败。  
**处理**: 在 **Linux 原生目录**（Ubuntu 主机或 WSL 内完整 `npm ci`）执行；Windows 可跑等价 P0：`pytest`、`compileall`、前端 `test:unit`/`type-check`/`build`。  
**参考**: `progress.md` 测试基线表

### `backend/scripts/*.sh` CRLF

**现象**: 容器内 `/bin/sh\r` 启动失败。  
**处理**: 保持 LF；仓库 `.gitattributes` 已约束 `*.sh text eol=lf`。

### 前端 `npm run lint` 副作用

**现象**: `--fix` 污染 diff。  
**处理**: 只读校验用 `npm exec oxlint .` 与 `npm exec eslint .`。

### Web Push 公钥来源

**现象**: 仅配置 `VITE_WEB_PUSH_PUBLIC_KEY` 与线上一致性漂移。  
**处理**: 以 `GET /api/v1/push-subscriptions/config` 为准；env 仅 fallback。

---

## 架构边界（非 Bug，易误判）

### 工作流 E 与图引擎未统一

**说明**: `task_templates` 与 `WorkflowGraphTemplate` 两套运行时并存；任务中心读侧已 graph-first，**不等于** E 已合并为图模板。  
**参考**: `decisions.md` ADR-005、`domains/workflow-graph-engine.md`

### Legacy 工作流 E 后端（待删除）

**说明**（@ `0.89.0`）:

| 层 | 状态 |
|----|------|
| 前端模板页 | **已移除** Legacy E Tab / CRUD；唯一入口为图模板列表 + 实例化（用户可见名「任务模板」） |
| 后端 `task_templates` API / `TaskTemplateService` | **仍保留**；运行中 E 实例与 `decideStepRun` 仍可用 |
| 删除时机 | **待删除** — **B-12** backlog（TCE Phase 5 未纳入；需迁移方案） |

**实例化路径**: `POST /api/v1/workflow-graph/templates/{id}/runs`

### 任务中心 TCE（Phase 1–5 ✅）

**说明**（@ 2026-06-21）：[`plans/task-center-enhance.md`](./plans/task-center-enhance.md) 主体已落地；**全貌见 [`domains/task-center.md`](./domains/task-center.md)**。

| 原缺口 | 状态 |
|--------|------|
| B-01 节点 graph 投影 | ✅ |
| B-02/B-07 列表 LIMIT / tracking 去重 | ✅ |
| B-03 department 迁移 | ✅ |
| B-04/F-01 batch hydration | ✅ |
| B-05/B-15 用户态 + Run 列 | ✅ |
| B-06/B-11/F-06 部门统计 + Run API | ✅ |
| B-09 分页 | ✅ |
| B-16/F-17 多部门实例化 | ✅ |
| B-08/B-13/B-14/F-13–F-16 Phase 5 清理 | ✅ |

**仍开放**：B-12（E 后端）、F-05（Shell 拆分）、F-10–F-12（抛光）。

### 图模板实例化：发起部门（TCE Phase 4 ✅）

**说明**（@ 2026-06-21）:

- **B-16**：`ParticipantPolicyDefinition.scope` 默认 `instance_department`；实例 `department_id` 优先于 seed policy。
- **F-17**：Dialog 默认/必选/可改发起部门；preview 与 submit 显式传 `department_id`。
- 详见 enhance **§6.2.1** 与 [`domains/task-center.md`](./domains/task-center.md) 场景 F。

### 视频 v1 图模板开关默认关闭

**说明**: `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED` 默认 `false`；批次/fork API 需显式开启。  
**参考**: `decisions.md` ADR-006

### 生命周期联动为显式绑定

**说明**: 非规则化默认映射；事件须带 `task_template_id` / `workflow_definition_id` 才 worker 触发。  
**参考**: `domains/hr-org.md`

---

## 测试与基线漂移

| 项 | 状态 | 说明 |
|----|------|------|
| pytest migration skip | 1 skipped @ `98ad370` | `test_migrations.py` 需 PostgreSQL；凭据错误时 skip，非失败 |
| 工作区 mass deletion | 2026-06-18 已恢复 | 409 文件 `D` → `git restore .`；跑测试前务必 `git status` |
| docker-gui 18/18 | 沿用 2026-05-20 基线 | 本机未重跑时需 Compose 栈 |
| Playwright mock | **9/9** @ `98ad370` | login + task-center + workflow-video-v1 |
| Playwright live | 未纳入每次基线 | 多账号见 `workflow-video-v1-multi-account-e2e-guide.md` |
| eslint | 8 errors | 非 release 阻塞，待清理未使用变量 |
| Ubuntu 最小回滚 | **暂缓** | 原 P0，用户决定上线前再练 |

**基线 ID**: `2026-06-18-main-45954eb`（见 `progress.md`「测试基线」）

---

## 生产与部署

- `FRONTEND_APP_URL` 生产必填（邀请链接避免 localhost）
- README 若写「缺 production compose」与 `docker-compose.prod.yml` 冲突 → **文档漂移**，以实际文件为准
- 在线 Ubuntu 演练已记录（Stage 2 Phase 6）；**最小回滚路径**暂缓至上线前

---

## 图引擎相关

### ORM 懒加载导致图实例详情 500

**原因**: `model_validate(ORM)` 触发 `node_instances` 异步懒加载。  
**修复方向**: 详情 API 用显式列 + 已查询集合组装 Pydantic（已实现，见 `workflow_graph_engine.py`）。

### 深度打回与 `max_iterations`

**说明**: 超出上限阻止；旧节点只读；前端展示 V{n} 角标。

---

## 汇报中心历史

**现象**: PostgreSQL enum 持久化与 ORM 不一致（2026-04 已修复）。  
**处理**: `build_value_enum()` 按枚举值持久化；见 `backend/app/core/db_types.py`。

---

## 追加记录

<!-- 新坑位：日期 + 现象 + 根因 + 解决方案 -->
