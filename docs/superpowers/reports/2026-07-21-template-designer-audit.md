# 图模板设计器审计报告

**日期**: 2026-07-21（会话执行日 2026-07-22）  
**范围**: `/task-templates` 列表 + `/task-templates/:id/edit` 设计器 + `WorkflowGraphTemplateAdminService`  
**性质**: 探索与差距报告（无实现代码）

---

## 已读文件清单

### Memory-bank（目标架构）
- `memory-bank/runtime/active-task.md`
- `memory-bank/knowledge/project-brief.md`
- `memory-bank/knowledge/domains/task-center.md` §7 / 附录 A
- `memory-bank/knowledge/contracts/database/graph-engine-schema.md`

### Frontend（实际读取）
| 文件 | 原因 |
|------|------|
| `frontend/src/views/GraphTemplateDesignerView.vue` | 设计器主 UI（归档按钮、模板类型） |
| `frontend/src/components/workflow/GraphTemplatesPanel.vue` | 模板列表操作列 |
| `frontend/src/views/TaskTemplatesView.vue` | 列表页壳层 |
| `frontend/src/components/workflow/GraphTemplateEditDialog.vue` | 「改名」弹窗 |
| `frontend/src/api/workflow-graph.ts` | 前端 API 封装 |
| `frontend/src/utils/workflowVideoSchema.ts` | 实例化准入（`run_kind`） |

### Backend（实际读取）
| 文件 | 原因 |
|------|------|
| `backend/app/models/workflow_graph.py` | `workflow_graph_templates` 字段 |
| `backend/app/core/enums.py` | `WorkflowGraphTemplateStatus` |
| `backend/app/schemas/workflow_graph.py` | StatusUpdate / Summary schema |
| `backend/app/api/routes/workflow_graph_engine.py` | 模板 CRUD / status 路由 |
| `backend/app/services/workflow_graph_template_admin_service.py` | 状态机、列表过滤、归档副作用 |
| `backend/app/services/workflow_video_template_seed_data.py` | `run_kind` / `ui_profile` 种子事实 |

### 未展开（若后续实现需读）
- `workflow_video_instantiation_service.py` / `workflow_video_fork_service.py` — 运行时如何消费 `run_kind`
- `workflow_graph_template_schedule_service.py` — schedulable 与 batch 耦合
- `GraphTemplateDesignerView.spec.ts` / `TaskTemplatesView.spec.ts` — 补测基线

---

## 1. 归档功能现状

### DB level
- 表 `workflow_graph_templates.status` 使用枚举 `WorkflowGraphTemplateStatus`：`draft` | `active` | `archived`。
- Schema 约定：ACTIVE/ARCHIVED 定义不可原地编辑；发布新版本时同 `base_code` 旧 ACTIVE 会被归档。
- **已有** `ARCHIVED` 值；无独立 `archived_at` / `archived_by` 列（仅靠 `status` + timestamps）。

### API level
| 能力 | 现状 |
|------|------|
| 显式归档 | **存在**：`PATCH /api/v1/workflow-graph/templates/{id}/status`，body `{ "status": "archived" }` → `update_status` 直接设 `ARCHIVED` |
| 发布连带归档 | **存在**：draft→active 时 `_archive_sibling_active_templates` 将同族其它 ACTIVE 置 ARCHIVED |
| 专用 `/archive` 路由 | **无**（通用 status 端点即可，非缺口） |
| 前端 API 封装 | **缺失**：仅有 `publishGraphTemplate`（写 `active`）；**无** `archiveGraphTemplate` / 通用 `updateGraphTemplateStatus` |
| Manage 列表 | **排除 ARCHIVED**：`list_manageable_templates` 只返回 `DRAFT` + `ACTIVE` |
| 实例化列表 | 仅 ACTIVE（`list_active_templates`） |

`update_status` 对 `ARCHIVED` **几乎无前置校验**（任意当前状态都可落到 archived）。删除规则明确：仅 draft 可删；已发布只能归档——但 UI 未露出该路径。

### UI level
| 表面 | 归档按钮 / 动作 |
|------|-----------------|
| `GraphTemplatesPanel` | **无**。操作：设计 / 复制 / 改名 / 删除(draft) / 实例化 |
| `GraphTemplateDesignerView` | **无**。操作：校验 / 试跑 / 导入导出 / 保存 / 另存新版本 / 发布 |
| `GraphTemplateEditDialog` | **无** |

删除提示写「已有运行实例的模板不可删除。请先归档相关 Run。」——指向的是 Run 归档语义，不是模板 `status=ARCHIVED`。

### 修复方案
1. **P0 — UI + 前端 API**  
   - 在 `workflow-graph.ts` 增加 `archiveGraphTemplate(id)` → `PATCH .../status { status: 'archived' }`。  
   - 列表（active 行）与设计器（非 draft）增加「归档」按钮 + 确认框。  
2. **P1 — 列表与可发现性**  
   - Manage 列表增加状态筛选（含 archived）或「已归档」Tab；否则归档后模板从管理视图消失且无法回看。  
3. **P1 — 后端收紧（可选）**  
   - 仅允许 `active → archived`（draft 继续用删除）；归档前可选检查 ACTIVE schedules。  
4. **P2 — 取消归档**  
   - 若产品需要恢复：`archived → active` 须处理同族唯一 ACTIVE 约束（与 publish 归档兄弟对称）。

**结论：缺的是前端按钮 + API 客户端封装；后端 status 端点已具备归档能力。** 连带缺口是归档后不可见。

---

## 2. 模板类型问题（批次 vs 制作）

### 当前分类方式
- **存储位置**：`workflow_graph_templates.config` JSONB 键 `run_kind` ∈ `{batch, production}`。  
  - **不是** DB 列，**不是** `source_type`（`source_type` 属于 Task）。  
  - API 读模型把 `config.run_kind` **投影**为 summary/detail 顶层字段 `run_kind`。
- **种子数据**：`topic_meeting_batch_v1` → `run_kind: batch`；`video_production_per_topic_v1` → `run_kind: production`。
- **节点侧已有更贴近引擎的概念**：节点 `config.ui_profile`（如 `video_n1_capture` / `video_batch_root` / `video_production_step`）；ORM `node_type` 仅为 `task|approval|notice`，**不含** batch/production。

### UI 如何使用
| 位置 | 行为 |
|------|------|
| 设计器「模板类型」 | Radio：批次 / 制作；写入 `config.run_kind`；文案写死「制作不可直接实例化」 |
| 列表「类型」列 | Tag：批次 / 制作 / 图 |
| 实例化 | `templateSupportsDirectInstantiation`：`run_kind === 'production'` → 禁用 |
| 改名弹窗 | 只读展示 `run_kind` |
| 任务详情等运行时 | 用 **instance/task metadata** 的 `run_kind`（实例化时从模板 config 拷贝），驱动 batch ROOT / production 面板 |

### 与新引擎的冲突
新引擎模型是 **templates → nodes → edges → instances**：

- 「批次」语义应对应 **图形态**（multi_instance 采集 + 汇总 + fork 边/子模板），以及 **ROOT / 聚合节点** 的 `ui_profile`，而不是整张模板的互斥类型标签。
- 「制作」应对应 **制作链节点序列**（`video_production_step` 等），或「仅由 fork 创建的子 Run」，而不是第二个模板品种单选。
- 把 `run_kind` 提成「模板类型」会：
  1. 强制一模板一角色，阻碍「单模板多形态 / 通用 DAG」；
  2. 与节点 `ui_profile` 双轨真相；
  3. 把产品概念（视频选题会）写死进通用设计器。

实例级 `context.run_kind` 作为 **运行时标签** 仍合理；问题在 **authoring 把模板属性当成类型系统**。

### 修复方案
1. **短线（P1）— UX 降级**  
   - 去掉设计器「模板类型」主 radio；改为高级/派生字段或只读提示。  
   - 列表「类型」改为结构摘要（如「可直接发起 / 仅 fork」或入口节点 profile），不再叫批次/制作。  
2. **中线（P1）— 准入规则去耦**  
   - 直接实例化条件改为显式策略，例如 `config.instantiation.mode = direct|fork_only`，或由「是否存在可启动入口 + 无 parent-only 标记」推导。  
   - Schedulable / fork 校验改读图结构或显式 flag，而非 `run_kind == batch`。  
3. **长线（P2）— 单一真相在节点**  
   - Authoring 强调节点 `ui_profile` / `kind`（multi_instance、aggregate、production step）。  
   - 实例化时由引擎根据入口节点与 `child_template_code` / fork 配置写入 instance `run_kind`（兼容视频 v1），模板 config 不再要求用户手选。  
4. **迁移**  
   - 存量 `config.run_kind` 保留为兼容只读，直到实例化/调度/fork 全部改读新规则后再 deprecate。

---

## 3. 整体差距分析

目标能力（领域文档）：模板可 **创建、编辑、归档、列表、搜索**；设计器对齐图引擎（nodes/edges/config/context_schema）；减少 JSON 手工编辑（F-26）。

### 已有功能

| 能力 | 状态 |
|------|------|
| 创建空白草稿 | ✅ |
| 克隆 / 另存新版本 | ✅ |
| 列表（manage: draft+active） | ✅ 无搜索 |
| 设计器编辑节点/边/配置 | ✅ 部分仍 JSON |
| 保存草稿 | ✅ |
| 校验 / dry-run | ✅ |
| 发布（draft→active） | ✅ |
| 导出 / 导入 JSON | ✅ |
| 删除 draft（无实例） | ✅ |
| 部门 scope / pools / participant_policies | ✅ 表单已有 |
| schedulable / on_complete | ✅ |
| 实例化（非 production） | ✅ |
| Run 计数统计列 | ✅ manage 列表 |
| **显式归档** | ❌ UI |
| **浏览已归档** | ❌ |
| **搜索** | ❌ |
| **context_schema 编辑** | ❌ 设计器未暴露 |
| **节点 ui_profile 结构化编辑** | ❌ 埋在 config JSON |
| **launch_schema / routing 去 JSON** | ⚠️ F-26 follow-up |

### 额外发现的一致性问题
- 设计器对 **非 draft** 提供「保存设置」→ `PATCH /templates/{id}`，但后端 `update_template` **拒绝**非 draft（须 fork 新版本）。「改名」弹窗同理。产品文案与契约不一致。
- Schema 写 ACTIVE/ARCHIVED 不可原地编辑；UI 仍暗示可改设置。

### Missing（汇总）

| ID | 缺口 | 优先级 |
|----|------|--------|
| M-01 | 归档按钮 + `archiveGraphTemplate` 客户端 | **P0** |
| M-02 | Manage 列表可见/筛选 ARCHIVED | **P1** |
| M-03 | 去掉/降级模板级「批次/制作」类型；实例化准入与 `run_kind` 解耦 | **P1** |
| M-04 | 修复 active「保存设置 / 改名」与后端不可变契约（禁用或改为 fork+edit） | **P1** |
| M-05 | 列表搜索（name/code）与状态过滤 | **P1** |
| M-06 | 节点 `ui_profile` / 入口形态结构化 authoring | **P2** |
| M-07 | `context_schema` 设计器入口 | **P2** |
| M-08 | launch_schema / routing 表单化（F-26 剩余） | **P2** |
| M-09 | archived→active 恢复策略（若需要） | **P2** |

### 优先级建议

- **P0**：露出归档能力（API 已有，补 UI + 客户端）；否则 ACTIVE 模板只能靠「发布兄弟版本」被动归档，或卡在「不可删除」。  
- **P1**：归档可发现性；模板类型去属性化；修正 active 编辑契约；搜索/筛选。  
- **P2**：节点级 profile / context_schema / 剩余 JSON 表单化；取消归档策略。

---

## 结论（一句话）

归档在 **DB + PATCH status API** 已齐，缺 **UI 与前端封装**（且列表故意隐藏 archived）；「批次/制作」仍落在 **`config.run_kind` 模板属性**，与图引擎「节点类型 / ui_profile」双轨冲突，应降级为运行时派生标签并改实例化准入；整体 CRUD 骨架已有，缺口集中在归档 UX、搜索、契约一致性与 F-26 结构化 authoring。
