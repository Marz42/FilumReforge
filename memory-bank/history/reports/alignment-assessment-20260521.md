# memory-bank 与实现对齐评估（2026-05-21）

**审查范围**: commit `36c6a77`（`main`）  
**审查目的**: Stage 2 Phase 6 收口、测试基线固化、IA 后体验补丁文档对齐  
**关联**: [`memory-bank/progress.md`](../../progress.md)、[`alignment-assessment-20260422.md`](./alignment-assessment-20260422.md)

---

## 1. 当前对齐度概览

| 维度 | 对齐度 | 说明 |
| --- | --- | --- |
| 阶段与交付状态 | **高** | Stage 2 Phase 0–6、IA A–F、工作流 Phase 11-A–G 均在 `progress.md` 标为 done |
| 架构与模块边界 | **高** | 本次已补 Dialog 建任务、备忘 title、附件 content API、任务搜索 |
| 数据库 / 迁移 | **高** | `20260519_01_task_memo_title` 已写入 `architecture.md` §10.25 |
| API 与前端入口 | **高** | `user-manual` v1.2 与 `TaskCenterView` / `GlobalMemoFloat` 一致 |
| 部署 / 发布 | **中高** | 在线 Ubuntu 主机演练已记入 progress；**回滚未演练**（已知遗留） |
| 测试 / 基线 | **高** | 2026-05-21 基线：pytest 153、vitest 106/106 |
| 后续计划 | **高** | README、`implementation-plan`、`improvements-stage2` §11 与 progress「当前规划焦点」一致 |

---

## 2. 已对齐事实（证据）

- **Stage 2 Phase 6 done**：`progress.md` Stage 2 表、在线主机演练记录、测试基线表。
- **工作流图引擎 Phase 11-F/G**：`TASK_CENTER_V2_ENABLED` 默认 true；任务中心 graph-first 读路径。
- **UI IA Phase A–F**：commits `51d2331`…`50c32c8` 与 `ui-refactor-spec-v2.md` 状态 delivered。
- **IA 后补丁**（`ae79023`–`36c6a77`）：`progress.md` 专表 + `architecture.md` v3.12.0。
- **邀请制注册**：Stage 2 Phase 5 done，三处文档一致。
- **附件鉴权下载**：`GET /api/v1/attachments/{id}/content`（`backend/app/api/routes/attachments.py`）。

---

## 3. 本次修复的文档漂移

| 严重度 | 类型 | 问题 | 证据 | 处理 |
| --- | --- | --- | --- | --- |
| 高 | 文档漂移 | README / user-manual 仍写建立任务 Drawer | `README.md`、`user-manual.md` | 已改为 Dialog（v1.2） |
| 高 | 文档漂移 | `architecture` 缺 `task_memos.title`、content API | `architecture.md` §6.4、§10.25 | 已补 |
| 中 | 文档漂移 | `progress` Stage 2 Phase 6 仍为 in_progress | `progress.md` | 已标 done + 基线 |
| 中 | 文档漂移 | Step 3 / Phase 1 仍写备忘/模板主标签 | `progress.md` | 已改为 inbox/tracking/history |
| 中 | 文档漂移 | 测试数字过时（151/96） | `progress.md` | 已更新为 153/106 |
| 低 | 文档漂移 | `alignment-assessment-20260422` 停在 Step 7 | 历史报告 | 保留；本报告 supersede 阶段状态 |

---

## 4. 测试基线（2026-05-21-main-36c6a77）

详见 [`progress.md`](../../progress.md)「测试基线」。

| 层级 | 结果 |
| --- | --- |
| P0 pytest | 153 passed |
| P0 vitest | 29 files / 106 tests passed |
| P0 type-check / build / compileall | PASS（Windows 原生 Node + backend venv） |
| P1 docker-gui | 未重跑；沿用 2026-05-20 18/18 |
| P2 playwright mock/live | 未重跑（Phase 11-G 独立层） |
| `check-release.sh` | Windows 等价 P0 通过；WSL 挂载盘执行受 rolldown 绑定限制 |

**代码侧单测修复**（与 `222f3d9` / `36c6a77` 对齐，计入本基线）：

- `backend/tests/test_services.py`：handler 展示名 `startswith` 断言
- `frontend/tests/OverviewTodoWidget.spec.ts`：待办/汇报分栏
- `frontend/tests/MessagesView.spec.ts`：`createdRange` 赋值

---

## 5. Stage 2 Phase 6 关闭结论

- **关闭条件已满足**：在线 Ubuntu 主机演练（用户确认）、开发机全量单测基线、文档与代码事实对齐。
- **明确遗留（不阻塞 done）**：
  - Ubuntu **最小回滚路径**未演练
  - 本机未重跑 docker-gui / Playwright（沿用或待下次刷新）
  - `eslint` 8 errors（非发布闸门）
  - 生产机 `check-release.sh` 须在 Linux 原生仓库路径执行

---

## 6. 建议的下一步（与 progress 一致）

1. Ubuntu 最小回滚演练  
2. 工作流 E 与 `WorkflowGraphTemplate` 产品级统一  
3. 生命周期规则 UI  
4. 公开/审批式注册、通知适配器深化  
5. 大版本前刷新 docker-gui / Playwright 基线  

---

## 7. 审查方法

- `git log --oneline -20`
- 对照 `backend/app/api/routes/`、`frontend/src/views/TaskCenterView.vue`、`GlobalMemoFloat.vue`
- 执行 `pytest`、`npm run test:unit -- --run`（Windows 开发机，2026-05-21）
