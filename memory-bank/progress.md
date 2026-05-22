# Project Filum 进度记录

## 测试基线（Test Baseline）

| 字段 | 值 |
| --- | --- |
| `baseline_id` | `2026-05-21-main-36c6a77` |
| `commit` | `36c6a77`（`feat(ui): task center UX polish, memos, and overview layout`） |
| `runner_os` | Windows 11 + `backend/.venv`（Python 3.11）；前端 `npm ci` 后原生 Node |
| `pytest` | **153 passed**（`backend/.venv/Scripts/python.exe -m pytest`，约 98s） |
| `compileall` | PASS（`python -m compileall -q app tests`） |
| `vitest` | **29 文件 / 106 用例** 全绿（`npm run test:unit -- --run`） |
| `type-check` / `build` | PASS（`npm run type-check`、`npm run build`；Vite chunk size 为信息性警告） |
| `check-release.sh` | **Windows 等价 P0 全绿**；经 Git Bash/WSL 直跑时因跨平台 `node_modules`（rolldown 绑定）与无 `python` 于 PATH 可能失败——生产/Ubuntu 主机应在 Linux 原生目录执行 `bash scripts/check-release.sh`（见在线演练记录） |
| `eslint` | 8 errors（`npm run lint`，非 `check-release` 阻塞项；含未使用变量等待清理） |
| `docker-gui` | **未在本机重跑**（Compose 栈未启动）；沿用 **2026-05-20** 基线 **18/18** @ `http://127.0.0.1:8080`，规格见 `frontend/e2e/docker-gui-verification/docker-gui-verification.spec.ts` |
| `playwright_mock` / `playwright_live` | 未纳入本次基线重跑（Phase 11-G 独立层；见 `memory-bank/plans/workflow-refactor-implementation-plan.md` §16.9） |
| `notes` | 单测已对齐 IA 后 UI：`OverviewTodoWidget` 待办/汇报分栏、`MessagesView` 时间范围 `createdRange`、handler 展示名 `name（email）`；`vite-plugin-vue-devtools` peer 警告不阻断 build |

## 视频工作流 v1（workflow-video-v1）

排期主文档：`memory-bank/plans/workflow-video-v1-implementation-plan.md`（v2.0）。W0 ADR：`memory-bank/plans/workflow-video-v1-w0-adr.md`。

### W0 测试命令（阶段出口，每阶段必跑）

| 层 | 命令 | W0 结果 |
| --- | --- | --- |
| 后端 W0 | `pytest -q tests/test_workflow_video_w0_baseline.py tests/test_settings.py::test_settings_parse_workflow_feature_flags` | **10 passed** |
| 前端 W0 | `npm run test:unit -- --run tests/workflowVideoW0Baseline.spec.ts` | **2 passed** |
| 编译 | `python -m compileall -q app tests`（backend） | PASS |

| W 阶段 | 状态 | 结论 |
| --- | --- | --- |
| W0 基线冻结 | done | v2 计划、architecture 摘要、W0 ADR、`workflow_video_policy`、前后端 W0 基线测试（10+2）；commit `dea816c` |
| W1 模型与契约 | done | 迁移 `20260522_01`、`workflow_video` schemas、图模型字段、W1 测试 9+1；W1-5 留 W3 |
| W2 参与者绑定 | done | `ParticipantResolutionService`、`preview-participants` API、规则 `context_var`/`department_pool`；测试 8+1+1 |
| WF 表单引擎（后端） | done | `WorkflowVideoFormService`、submit-capture / submissions / finalize-topics API；fork 留 WFK；测试 5+1+2 |
| W3 图实例化 v2 | done | `WorkflowVideoInstantiationService`、`POST .../templates/{id}/runs`、multi_instance、ROOT Task、`schema_snapshot`；测试 4+1+1 |

### W1 测试命令

| 层 | 命令 | 结果 |
| --- | --- | --- |
| 后端 W1 | `pytest -q tests/test_workflow_video_w1_contracts.py` | **9 passed** |
| 前端 W1 | `npm run test:unit -- --run tests/workflowVideoW1Contracts.spec.ts` | **1 passed** |
| 类型 | `npm run type-check` | PASS |

### W2 测试命令

| 层 | 命令 | 结果 |
| --- | --- | --- |
| 后端 W2 | `pytest -q tests/test_workflow_video_w2_participant_resolution.py tests/test_api.py::test_w2_preview_participants_api` | **9 passed** |
| 前端 W2 | `npm run test:unit -- --run tests/workflowVideoW2Api.spec.ts` | **1 passed** |

### WF 测试命令

| 层 | 命令 | 结果 |
| --- | --- | --- |
| 后端 WF | `pytest -q tests/test_workflow_video_wf_form_engine.py tests/test_api.py::test_wf_submit_capture_and_finalize_topics_api` | **6 passed** |
| 前端 WF | `npm run test:unit -- --run tests/workflowVideoWfApi.spec.ts` | **2 passed** |

### W3 测试命令

| 层 | 命令 | 结果 |
| --- | --- | --- |
| 后端 W3 | `pytest -q tests/test_workflow_video_w3_instantiation.py tests/test_api.py::test_w3_create_graph_template_run_api` | **5 passed** |
| 前端 W3 | `npm run test:unit -- --run tests/workflowVideoW3Api.spec.ts` | **1 passed** |
| W4 编排钩子 | pending | — |

## 当前阶段状态

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| Phase A / 文档与工程基线 | done | 文档入口、脚手架、基础编排已完成 |
| Phase 1 / Foundation | done | 用户、组织、档案、附件、任务基础、异步通知骨架已完成并通过用户点击验证 |
| Phase 2 / Collaboration & Stats | done | 状态机、评论留痕、审计日志、ARQ 提醒 worker、统计与协同任务页已完成并通过用户简单测试 |
| Phase 3 / HR Governance & Org Modeling | done | 代码已实现、修复 PostgreSQL 迁移命名问题，并通过用户手动验测 |
| Phase 4 / Workflow Engine & Messaging | done | 模板、审批流、自动化、消息中心与多视图已完成，并通过用户手动验测 |
| Phase 5 / Knowledge, AI Router & Experience | done | 知识库、RAG、AI Router、Push / PWA 已完成，后续进入文档收口、重构与测试强化 |

## 当前重构执行状态

| 步骤 | 状态 | 结论 |
| --- | --- | --- |
| Step 1 / 壳层导航重构 | done | 用户已确认通过，已完成分组导航、主入口改名、旧路由兼容跳转与聚合入口壳层 |
| Step 2 / 总览模块 | done | 已完成看板、公告、当前任务投影、总览聚合接口、总览页前端、归档 cron 与自动化回归，并通过用户手动验测 |
| Step 3 / 任务中心重构 | done | 已完成任务中心聚合工作台、`task-center` 聚合接口、`task_memos` 领域、权限重构与前后端回归；后续体验收口为 Inbox-first：**待处理 / 跟踪 / 历史** 三主筛选；**个人备忘** 与 **任务模板** 已迁出为全局浮窗 + `/task-templates`；建立任务现为页头 **居中 Dialog**（见 IA 后补丁 `36c6a77`） |
| Step 4 / 汇报中心落地 | done | 已完成 `report-center` 聚合接口、`reports` / `report_routes` 领域、逐级向上汇报 / 向下传达、可选审批挂接与前后端回归；已修复 PostgreSQL 500 根因，并通过用户手动验测 |
| Step 5 / 档案管理 & 用户管理合并 | done | 已完成 `/api/v1/people-management` 聚合接口与统一人员工作台；已完成全量自动化回归，并通过用户手动验测 |
| Step 6 / 消息中心联动与提醒收口 | done | 已完成消息中心聚合快照、来源 payload 规范化、用户级隔离、来源回跳与前后端全量回归，并通过用户手动验测 |
| Step 7 / 当前重构收口 | done | 已完成 memory-bank、README 与子目录 README 收口，已执行最终全量回归，并通过用户验测 |

## 下一轮工作流状态

| 工作流 | 状态 | 结论 |
| --- | --- | --- |
| 工作流 E / 结构化任务模板与多步骤协作 | in_progress | 首批实现已落地：模板实例 / 步骤运行态、逐步激活、多人扇出 / 汇聚、结构化设计器与实例快照已完成；当前进入回归、部署准备与后续深化 |
| 部署工程化收口 | done | 生产运行形态已收口；**Stage 2 Phase 6** 已记录在线 Ubuntu 主机演练与 Windows 开发机测试基线（见下表与「测试基线」）；**最小回滚路径**仍待单独演练 |

## 工作流重构 / 当前执行状态

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| Phase 0 / 基线冻结与术语对齐 | done | 已确认双层状态模型、旧任务映射口径、渐进切换策略与阶段测试出口，并形成 `memory-bank/plans/workflow-refactor-implementation-plan.md` 作为当前工作流重构基线 |
| Phase 1 / 任务中心信息架构重排 | done | 已移除任务中心顶部统计卡片；默认入口切到“待处理”；建立任务收敛到页头入口（现为 **Dialog**，见 `36c6a77`）；主筛选为 **待处理 / 跟踪 / 历史**；备忘与模板已独立；保留 `?selected=` 深链。已执行 frontend `npm run test:unit -- --run tests/TaskCenterView.spec.ts tests/TasksView.spec.ts tests/Router.spec.ts`、`npm run type-check`、`npm run build`，并通过用户验收 |
| Phase 2 / 图引擎核心模型落库 | done | 已完成后端落库实现：新增 `workflow_graph_templates`、`workflow_graph_template_nodes`、`workflow_graph_template_edges`、`workflow_graph_instances`、`workflow_node_instances`、`workflow_deliverables`、`workflow_outbox_events` 七张表，以及图模板状态、图实例状态、节点引擎态、节点业务投影态、outbox 事件状态枚举；已执行 backend `pytest -q tests/test_models.py -k "workflow_graph or node_instance or deliverable"`、`pytest -q tests/test_migrations.py`、`python -m compileall app tests`，并通过用户验收，可进入 Phase 3 |
| Phase 3 / 单步任务接入单节点实例 | done | 已完成后端首轮接入：新增 `WORKFLOW_GRAPH_ENGINE_ENABLED` / `TASK_CENTER_V2_ENABLED` / `WORKFLOW_WAIT_ANY_ENABLED` / `WORKFLOW_DEEP_REJECTION_ENABLED` 配置开关、`WorkflowGraphService` 单节点实例创建服务，并让 `TaskService.create_task_record()` 在开关开启且手动建任务时走 `WorkflowGraphInstance + WorkflowNodeInstance + Task` dual-write 路径；在该基线上又补了单节点交付物提交 / 验收通过 / 打回返工首轮动作，交付快照落到 `workflow_deliverables`，同时禁止 graph 手动任务通过通用状态流转直接跳过交付 / 验收。读取侧继续保持现有 `Task` / `TaskCenterService` 协议不变。已执行 backend `pytest -q tests/test_settings.py tests/test_services.py::test_task_service_creates_task_and_enqueues_notification tests/test_services.py::test_phase3_single_node_workflow_creation_projects_task_and_graph_entities tests/test_services.py -k "phase5_graph_task_supports_deliverable_review_and_rework_cycle" tests/test_api.py -k "phase3_create_task_api_uses_graph_engine or phase5_task_deliverable_review_api_flow or phase5_task_status_api_blocks_direct_review_and_done_for_graph_tasks"`、`python -m compileall app tests`，以及 frontend `npm run test:unit -- --run tests/TasksView.spec.ts tests/TaskCenterView.spec.ts`、`npm run type-check` |
| Phase 4 / 单步任务握手与转办 | done | 已完成 graph 手动任务接单 / 退回协商 / 转办首轮实现：图节点默认以 `ASSIGNED` 业务态创建，`TaskService` 与 `tasks` API 新增 `accept` / `reject` / `delegate` 动作，`todo -> doing` 需要先接受任务；`TaskCenterService` 兼容投影当前阶段为“待确认 / 已接受待开工 / 已拒绝待调整 / 待验收”，`TasksView` 已新增接单 / 协商 / 转办按钮与原因展示。已执行 backend `pytest -q tests/test_services.py::test_phase4_graph_task_requires_accept_before_start_and_updates_inbox_context tests/test_services.py::test_phase4_graph_task_reject_and_delegate_refresh_runtime_projection tests/test_api.py::test_phase4_task_acceptance_and_task_center_snapshot_flow tests/test_api.py::test_phase4_task_reject_and_delegate_api_refresh_task_center_snapshot`，以及 frontend `npm run test:unit -- --run tests/TasksView.spec.ts tests/TaskCenterView.spec.ts`、`npm run type-check`；graph runtime 直读与模板运行态接入仍待后续阶段实现 |
| Phase 5 / 单步任务交付、验收、返工 | done | 已在 Phase 3/4 基线上补齐单步交付验收首轮的质量评价与跟踪投影：`TaskService.review_task_deliverable()` / `tasks` API 现支持 `quality_score`，兼容 `Task.extra_metadata` 暴露最近质量评分，`TaskCenterService` / `task-center` API / `TaskCenterView` 同步展示待验收、最近提交时间、返工次数、质量评分等信号，`TasksView` 已提供验收评价与质量评分输入。已执行 backend `pytest -q tests/test_services.py::test_phase5_graph_task_supports_deliverable_review_and_rework_cycle tests/test_api.py::test_phase5_task_deliverable_review_api_flow`，以及 frontend `npm run test:unit -- --run tests/TasksView.spec.ts tests/TaskCenterView.spec.ts`、`npm run type-check` |
| Phase 6 / 多节点图运行时与实例读写 | done | 已完成 `WorkflowGraphService.create_multi_node_instance()` / `complete_node_instance()`、`workflow_graph_engine` API、顺序流 / fan-out / wait-all join 推进与实例收口；本轮又补实例级行锁、重复完成幂等保护、节点版本号递增，以及基于模板 `sort_order` 的稳定 `current_node_key` 解析。已执行 backend `pytest -q tests/test_services.py -k "phase6"`、`pytest -q tests/test_api.py -k "phase6 or workflow_graph"` |
| Phase 7 / Context、条件路由与 Notice | done | 已完成图引擎 Phase 7 首轮后端实现：`WorkflowGraphService.complete_node_instance()` 新增 `context_updates` 并回写 `WorkflowGraphInstance.context/context_version`；模板出边新增条件求值（`eq/neq/gt/gte/lt/lte/in/not_in/contains/exists`）与 `else` 默认分支；`Notice Node` 激活后自动完成并继续推进下游；新增 `OrganizationRelationService.suggest_notice_recipients()` 与 `POST /api/v1/workflow-graph/smart-notice-candidates` 接口，支持越级派发场景中间领导候选计算与人工增删。已执行 backend `f:/Lab/FilumReforge/.venv/Scripts/python.exe -m pytest -q tests/test_services.py -k "phase7_context or phase7_smart_notice"`、`f:/Lab/FilumReforge/.venv/Scripts/python.exe -m pytest -q tests/test_api.py -k "phase7_smart_notice_candidates_api"` |
| Phase 8 / Wait-Any、抢单与并发撤权 | done | 已完成图引擎 Wait-Any 首轮实现：`join_mode=any` 下任一并发上游先完成即推进下游，并将同批其余 `ACTIVATED/ACKNOWLEDGED` 节点自动置为 `TERMINATED + CANCELLED`，写入系统撤权标记并回收办理权限；`complete_node_instance()` 已拦截撤权节点迟到提交并返回 409。前端 `TaskTemplatesView` 已补或签风险提示与运行态撤权文案。新增 API 路由层集成测试覆盖撤权后提交冲突。已执行 backend `f:/Lab/FilumReforge/.venv/Scripts/python.exe -m pytest -q tests/test_services.py -k "phase8_wait_any_activates_downstream_and_terminates_peer_nodes"`、`f:/Lab/FilumReforge/.venv/Scripts/python.exe -m pytest -q tests/test_api.py -k "phase8_node_completion_api_blocks_terminated_node_submission"`，以及 frontend `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`、`npm run type-check` |
| Phase 9 / 深度打回与 Append-Only 版本链 | done | 已完成图引擎深度打回首轮实现：`WorkflowGraphService.deep_reject_to_upstream()` 校验上游可达性（基于 normal edge 正向传播），将可达链路中尚未收口的旧节点置为 `TERMINATED + CANCELLED` 并写系统审计标记，以 `iteration+1` 克隆目标节点及其尾链为新版本；目标节点 clone 置 ACTIVATED，其余置 PENDING；超过 `max_iterations` 返回 409 阻止；旧版本节点及其交付物只读保留。后端新增 `WorkflowNodeDeepRejectRequest` schema 与 `POST /api/v1/workflow-graph/node-instances/{id}/deep-reject` 端点；`TaskService.create_task` 在 extra_metadata 中写入 `workflow_node_iteration` 与 `workflow_deep_rejection_reason`；前端 `TasksView` 在迭代版本 >1 时展示"V{n}（系统深度打回重放）"标签与打回原因，`TaskTemplatesView` 在 `history_iteration_count > 0` 时展示"曾被系统打回重放"提示。已执行 backend `pytest -q tests/test_services.py -k "phase9_deep_reject"`（2 passed）、`pytest -q tests/test_api.py -k "phase9_deep_reject_api"`（1 passed），frontend `npm run test:unit -- --run tests/TasksView.spec.ts tests/TaskTemplatesView.spec.ts`（21 passed）、`npm run type-check`；Phase 9-F 全量回归：backend `pytest -q`（全部通过，含 `test_settings.py` 与 `test_task_collaboration_and_stats_api_flow` 修正适配 graph engine 启用状态），frontend `npm run test:unit -- --run`（19 files / 70 tests passed）、`npm run type-check` |
| Phase 10 / 图引擎能力前端化 | done | 将 Phase 7-9 已落地的图引擎能力完整暴露为业务可用界面。**10-A**：`TaskTemplatesView` 新增出口路由规则编辑器（IF 条件规则 + ELSE 兜底规则，含 context 字段 / 运算符 / 比较值三联下拉，目标步骤选择器），保存时校验 routing_rules 非空时必须包含 ELSE 兜底规则；`routing_rules` 写入 step `config`。**10-C**：新增 `frontend/src/api/workflow-graph.ts`（`getWorkflowGraphInstance`），`frontend/src/types/api.ts` 补充 `WorkflowGraphInstanceDetail` / `WorkflowNodeInstanceSummary` 等图引擎 TS 类型；`TasksView` 打开图任务详情时自动 fetch 图实例，在任务侧边栏展示节点板块列表（标题、engine_state 标签、V{n} 迭代角标、耗时）。**10-D**：`TaskCenterView` 任务跟踪表格标题列新增逾期标签（due_date < now && status != done），新增催办列（调用 `createTaskComment` 写入"【催办】"评论，loading 态按行隔离）。**10-E**：`handleSaveTemplate` 保存前检测 `join_mode=any` 步骤并弹 `ElMessageBox.confirm` 提示或签风险。全量回归：backend `pytest -q`（全绿），frontend `npm run test:unit -- --run`（19 files / 75 tests passed）、`npm run type-check`、`npm run build` |
| Phase 11-A / routing_rules 旧系统桥接 | done | 新建 `backend/app/services/condition_evaluator.py`（`is_else_condition` / `evaluate_condition` / `evaluate_routing_rules`，支持 eq/neq/gt/gte/lt/lte/in/not_in/contains/exists 与嵌套 all/any）；`WorkflowGraphService` 删除内联条件求值方法，改为引用 `condition_evaluator`；`TaskService._activate_ready_template_steps` 新增 `_routing_rules_allow_step_activation` 静态方法，在上游步骤有 `routing_rules` 时仅激活命中条件的目标步骤（无规则时完全向后兼容）；使用 `instance.payload` 作为条件求值上下文。已执行 `pytest -q test_services.py -k "phase11a"`（2 passed）；全量回归无新增失败（仅两个预存在失败，详见"当前已知问题"）。 |
| Phase 11-B / Takeover（管理员接管节点） | done | 已完成后端管理员接管能力：`WorkflowGraphService.takeover_node_instance()` 新增管理员权限校验、运行态校验、接管审计（写入 `node_instance.config.takeover`）与接管后节点重置（`ACTIVATED + ASSIGNED`）；新增 `WorkflowNodeTakeoverRequest` schema 与 `POST /api/v1/workflow-graph/node-instances/{id}/takeover` 接口。通知从同步发送切换为写 outbox 事件（由 Phase 11-C worker 异步投递）。已执行 `pytest -q tests/test_services.py -k "phase11b"`（2 passed）、`pytest -q tests/test_api.py -k "phase11_takeover_api"`（1 passed）。 |
| Phase 11-C / Outbox Pattern 可靠投递 | done | 已启用 workflow outbox 异步投递链路：新增 `backend/app/workers/workflow_outbox_worker.py`，实现 `process_workflow_outbox_events` 批量扫描 `PENDING/RETRYING` 事件并按 `attempt_count`、`available_at` 指数退避重试，成功置 `DISPATCHED`，失败超上限置 `FAILED` 并记录 `last_error`；`backend/app/workers/arq_worker.py` 注册 30 秒 cron；`WorkflowGraphService` 新增 `_write_outbox_event()` 并在 takeover 路径启用。已执行 `pytest -q tests/test_workers.py -k "phase11c"`（3 passed）与 `pytest -q tests/test_workers.py tests/test_services.py -k "phase11"`（7 passed）。 |
| Phase 11-D / 幂等与并发防御加固 | done | 已完成 11-D 收口：1）生产环境 `FRONTEND_APP_URL` 现在必须显式配置，邀请注册链接不再允许静默回落到 `http://localhost:5173`，并已同步更新 `backend/.env.production.example`、`infra/docker/.env.prod.example`、`infra/docker/docker-compose.prod.yml` 与 Ubuntu 部署手册；2）管理员接管 graph 节点后，会同步刷新手动 `Task` 投影（`assignee_id`、握手 metadata、任务中心标签“任务：管理员接管待确认”），避免 graph runtime 与兼容读模型脱节；3）`workflow_graph_engine` 的 `complete` / `deep-reject` / `takeover` 写接口已补事务提交，变更可跨会话持久化；4）`TaskService` 现在会阻止对 `COMPLETED/TERMINATED` graph 节点继续执行 accept / reject / delegate，避免兼容任务握手动作把已失效节点“复活”；5）已补齐 Wait-All / Wait-Any 重放、takeover 失效节点冲突、stale deep-reject 阻断，以及 complete / deep-reject API 重放稳定性回归。已执行 backend `pytest -q tests/test_services.py::test_phase11d_accept_blocks_when_graph_node_is_terminated tests/test_services.py::test_phase11d_reject_blocks_when_graph_instance_is_completed tests/test_services.py::test_phase11d_takeover_blocks_when_node_is_completed tests/test_services.py::test_phase11d_deep_reject_blocks_replay_from_stale_node_after_clone tests/test_api.py::test_phase11d_complete_api_replay_returns_stable_snapshot tests/test_api.py::test_phase11d_deep_reject_api_blocks_replay_from_stale_node`、`pytest -q tests/test_services.py -k "phase11b or phase11d or phase6_repeat_completion_is_idempotent_and_keeps_single_downstream_activation or phase11d_wait_all_join_replay_keeps_single_downstream_activation or phase8_wait_any_activates_downstream_and_terminates_peer_nodes or phase11d_wait_any_replay_keeps_single_downstream_activation or phase9_deep_reject" tests/test_api.py -k "phase11d or phase11_takeover or phase9_deep_reject_api_blocks_when_iteration_exceeds_limit or phase6_node_completion_triggers_downstream_activation or phase8_node_completion_api_blocks_terminated_node_submission"`，以及 `python -m compileall app tests`。 |
| Phase 11-E / 旧数据迁移脚本 | done | 已完成 11-E 首轮：新增 `LegacyTaskGraphMigrationService`、`backend/app/scripts/migrate_legacy_tasks_to_graph.py` 与 `backend/app/scripts/rollback_legacy_task_migration.py`，支持旧 `Task`（含带 `template_step_run_id` 的历史模板任务）按批次迁移为单节点 graph 投影、写回 `workflow_graph_instance_id/workflow_node_instance_id` 等 metadata 锚点、补建 `WorkflowDeliverable` 快照，并支持 `--dry-run` 与按批次 rollback；已同步更新 Ubuntu runbook。已执行 backend `pytest -q tests/test_services.py::test_phase11e_migrate_legacy_tasks_creates_graph_projection_and_deliverable_snapshot tests/test_services.py::test_phase11e_rollback_removes_graph_projection_and_restores_task_metadata`、`python -m compileall app tests`。 |
| Phase 11-F / 默认路径切流 | done | 已完成 11-F 首轮：`TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 在 `TASK_CENTER_V2_ENABLED` 下改为 graph-first with legacy fallback，优先读取 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable` 投影，修正 migrated review task 的 inbox 归属与 history 完成态；`backend/app/core/config.py` 已将 `WORKFLOW_GRAPH_ENGINE_ENABLED` 与 `TASK_CENTER_V2_ENABLED` 默认值切到 `true`，环境模板与 production compose 也已同步为默认 graph-first、显式关闭才回退。已执行 backend `pytest -q tests/test_settings.py tests/test_services.py::test_phase11f_task_center_v2_routes_migrated_review_task_to_creator_inbox tests/test_services.py::test_phase11f_task_center_v2_history_prefers_graph_completed_state tests/test_api.py::test_phase11f_task_center_api_uses_graph_first_for_migrated_review_task`、`python -m compileall app tests`。 |
| Phase 11-G / 文档收口、前端回归与 Playwright 基线 | done | 已完成 docs gate、前端可测性加固、Playwright mock/live 双轨基线与前端回归收口：新增 `frontend/playwright.config.ts`（mock API E2E）、`frontend/playwright.live.config.ts`（隔离 Compose + sample data 的真实后端 E2E）、`frontend/e2e/live/docker-compose.playwright-live.yml`、live 启停 helper 与真实任务创建场景；补齐登录页 / 任务中心 / 任务详情稳定锚点，并完成 frontend `npm run test:unit -- --run`、`npm run type-check`、`npm run build`、`npm run test:e2e`、`npm run test:e2e:live`。Playwright 仍保持独立验证层，未并入默认发布脚本；Linux/Ubuntu 近似环境上的最终发布演练继续留在部署工程化主线。 |

## Stage 2 / 当前实施周期

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| Stage 2 Phase 0 / 基线冻结与阶段确认 | done | 已将实施计划统一迁至 `memory-bank/plans/improvements-stage2-implementation-plan.md`，并明确当前周期使用 Stage 2 命名，避免与历史 Phase 2 冲突 |
| Stage 2 Phase 1 / 前端体验收敛 | done | 首页与任务中心体验收口已完成，并已通过前端 `test:unit`、`type-check`、`build` 验证；后续阶段继续以该结果为前端基线 |
| Stage 2 Phase 2 / 模板工作台与工作流 E 治理 | done | 已完成三批收口：1）结构化设计器前端校验与流转关系表达；2）模板版本语义、结构锁定与新建版本入口、调度最近执行结果、实例整体进度与步骤迭代展示；3）按模板实例串行化激活入口，补齐 fan-out / join 下游步骤重复激活约束，并补 worker 成功/失败状态回写回归。已执行 backend `pytest -q tests/test_models.py tests/test_services.py tests/test_api.py tests/test_workers.py`、`python -m compileall app tests`，以及 frontend `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`、`npm run type-check`、`npm run build` |
| Stage 2 Phase 3 / 生命周期事件联动 | done | 已完成后端首轮联动：生命周期事件可显式绑定任务模板 / 审批流目标，事件新增触发状态、错误、尝试次数与已生成实例锚点；`HRLifecycleService` 已接入异步入队与 worker 执行，覆盖入队、成功联动、失败回写与幂等场景。已执行 backend `pytest -q tests/test_services.py -k "lifecycle_event_automation or phase3_services_apply_lifecycle_events"`、`pytest -q tests/test_api.py -k "profile_event_api_accepts_lifecycle_automation_targets or people_management" tests/test_workers.py -k "employment_event_automation or run_due_task_schedules_records_failure_state"`、`pytest -q tests/test_migrations.py`、`python -m compileall app tests`；等待用户测试后再进入 Stage 2 Phase 4 |
| Stage 2 Phase 4 / 消息中心深化 | done | 已完成首轮收口：消息通过 `attachment_links(target_type = notification_message)` 接入附件体系；消息中心补齐来源模块 / 回执状态 / 渠道 / 投递状态 / 时间范围组合筛选；详情页补附件、投递尝试次数与失败原因展示。已执行 backend `pytest -q tests/test_services.py -k "message_center_snapshot" tests/test_api.py -k "message_center_api"`，以及 frontend `npm run test:unit -- --run tests/MessagesView.spec.ts`、`npm run type-check`；等待用户测试后再进入 Stage 2 Phase 5 |
| Stage 2 Phase 5 / 注册与账号开通 | done | 已完成邀请制注册首轮落地：后端补 `users` 邀请字段、邀请生成 / 预览 / 激活 / 撤销服务与认证路由；登录页支持邀请预览与设置密码激活；人员工作台“新建账号”对话框支持“直接创建 / 邀请注册”双路径。已执行 backend `pytest -q tests/test_settings.py::test_settings_validate_invitation_options tests/test_services.py::test_auth_service_invitation_flow_create_accept_and_revoke tests/test_api.py::test_auth_invitation_api_flow`、`python -m compileall app tests`，以及 frontend `npm run test:unit -- --run tests/LoginView.spec.ts tests/AuthStore.spec.ts tests/PeopleManagementView.spec.ts`、`npm run type-check`；等待用户测试后再进入 Stage 2 Phase 6 |
| IA-0 / 用户说明书 v1 | done | [`memory-bank/handbooks/user-manual.md`](handbooks/user-manual.md) 已成稿并完成审阅批注；作为 UI 重构事实基线。 |
| IA-1 / UI Phase A（登录与设置） | done | 三场景登录、设置三分栏、改密 API；见 commit `51d2331`。 |
| IA-1 / UI Phase B（壳层与消息） | done | AppHeader、铃铛 Drawer、侧栏去消息；布局修复 `f4880f0`（`el-container direction=vertical`）。 |
| IA-2 / UI Phase C（任务中心） | done | Quick Chips + Master-Detail、GlobalMemoFloat、`/task-templates` 独立路由；见 commit `080f814`。 |
| IA-3 / UI Phase D（汇报中心） | done | Master-Detail + ReportComposeDrawer；见 commit `c3fec3a`。 |
| IA-4 / UI Phase E（组织管理） | done | 人员宽 Drawer + 锚点导航、部门树 Master-Detail；`PeopleManagementView.spec.ts` + `DepartmentsView.spec.ts` 通过。 |
| IA-5 / UI Phase F（总览 Dashboard） | done | 小组件化 HomeView、顶栏 DeadlineCountdown、消息/公告/待办 widgets；见 commit `50c32c8`。 |
| Stage 2 Phase 6 / 部署演练与全量回归 | done | **2026-05-21** 收口：开发机 **pytest 153**、**vitest 29/106**、`type-check`/`build`/`compileall` 通过（见「测试基线」）。**Docker GUI** 沿用 2026-05-20 **18/18**。**在线 Ubuntu 主机演练**已完成（见下「在线主机演练记录」）。**用户说明书** v1.2 与 IA 后补丁对齐。**遗留**：Ubuntu **最小回滚路径**未演练（不阻塞 Phase 6 done）。 |

### 在线主机演练记录（Stage 2 Phase 6）

按 [`handbooks/deployment-runbook-ubuntu-2404.md`](handbooks/deployment-runbook-ubuntu-2404.md) §19–§20，**在线生产/预发主机**已完成首轮上线验证（用户确认，2026-05-21）：

| 项 | 结论 |
| --- | --- |
| 部署路径 | Ubuntu 主机目录（如 `/srv/filum`），systemd `filum-backend` / `filum-worker` + Nginx |
| 发布 commit | `36c6a77`（与当前 `main` 基线一致） |
| `curl http://127.0.0.1:8000/healthz` | 通过 |
| `systemctl` backend / worker / nginx | active |
| HTTPS / 公网域名 | 浏览器可访问登录页与核心业务路由 |
| 浏览器冒烟 | 登录、总览、任务中心、汇报中心、消息、知识库可访问 |
| 服务器 `check-release.sh` | 已执行；生产机无 dev 依赖时 **pytest 记 WARN** 符合 runbook §19，非阻塞 |
| Push（若已配置） | 按环境启用验证 |
| **回滚演练** | **未演练** — 列入「当前规划焦点」第 1 项 |

### Stage 2 文档同步约定

- 每个 Stage 2 阶段完成后，必须先更新 `memory-bank/architecture.md` 记录实现事实、受影响模块职责与结构变化。
- 随后必须更新 `memory-bank/progress.md` 记录阶段状态、验证命令、验收结论与待用户测试项。
- 如果某阶段只涉及前端行为变化，也不能跳过 `architecture.md`；需要记录页面行为或模块职责变化。
- 阶段范围与排期以 `memory-bank/plans/improvements-stage2-implementation-plan.md` 为准；**文档物理路径**以 `memory-bank/README.md` 索引为准（`handbooks/`、`plans/`、`history/`、`archive/outdated/`）。**对齐审查报告**默认写入 `memory-bank/history/reports/alignment-assessment-YYYYMMDD.md`（见 `.github/prompts/memory-bank-alignment-review.prompt.md`）。

## IA 后体验补丁（2026-05-14 之后）

| Commit | 日期 | 内容 |
| --- | --- | --- |
| `ae79023` | 2026-05-20 | `GET /api/v1/attachments/{id}/content` 鉴权下载；前端 blob 拉取；文档与用户手册同步 |
| `2b062cf` | 2026-05-20 | 部门树新建根/子部门时详情面板进入可提交创建模式 |
| `222f3d9` | 2026-05-21 | 负责人/流程参与者展示为「姓名（邮箱）」；建任务流程与部门范围执行人优化 |
| `36c6a77` | 2026-05-21 | 建立任务 **Dialog** + 未保存关闭确认；备忘列表 + 新建/编辑 Dialog + 可选 `title`；`FilumDateTimePicker`；任务搜索与筛选摘要卡；总览待办/汇报分栏 widget；任务中心 V2 跟踪语义收紧 |

## 近期补丁 / 会话安全改造

| 项目 | 状态 | 结论 |
| --- | --- | --- |
| 第二批会话安全改造 | done | refresh token 已切换为 HttpOnly cookie，前端 access token 改为内存态，`/auth/logout` 已支持服务端撤销与清 cookie；已执行 backend `pytest -q`、`python -m compileall app tests` 与 frontend `npm run test:unit -- --run`、`npm run type-check` |
| 附件策略与汇报绑定 | done | `AttachmentService` 扩展白名单与分类型大小上限；`report` target + `ReportCreateRequest.attachment_ids`；`attachment_serializers`；前端三处上传预检与任务附件查看/下载；迁移 `20260515_01` |
| 图引擎写路径与 API 快照 | done | `WorkflowGraphService` 对 complete / takeover / deep-reject **commit**；接管同步 `Task` 投影（`manual` source）；`workflow_graph_engine` 显式字段组装 `WorkflowGraphInstanceDetailRead` |
| 测试与 Docker GUI E2E | done | `conftest` 支持仓库根 `pytest`；docker-gui **C1.2b** 使用 filechooser；`TasksView` 附件 testid 包裹层 + `initialSelectedTaskId` 列表就绪后再选中 |

## 当前已知问题

- **测试基线**（2026-05-21）：后端 **153 passed**；前端 **106/106**；无阻塞性单测失败。
- **Docker GUI**：本次开发机未重跑；沿用 2026-05-20 **18/18** @ `http://127.0.0.1:8080`。
- **`check-release.sh`**：须在 **Linux 原生** 仓库路径执行（避免 WSL 挂载盘 `node_modules` 的 rolldown 绑定问题）；Windows 开发机以「测试基线」中等价 P0 为准。
- **Ubuntu 最小回滚路径**：未演练（Phase 6 遗留，见「当前规划焦点」）。
- **eslint**：8 个 error（非发布闸门）；待后续清理未使用变量等。
- 生产前端 `npm ci && npm run build` 的 Vite 8 / `vite-plugin-vue-devtools` peer 警告不阻断构建。

## 已完成里程碑

### Phase A / 文档与工程基线

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 文档基线与标准入口 | done | 建立 `architecture.md`、`design-document.md`、`progress.md`、`plans/implementation-plan.md` 与 `memory-bank/README.md` 索引约定 | 已核对文件存在与引用一致性 |
| 前端脚手架 | done | Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus | 已执行前端单元测试、构建与 lint |
| 后端脚手架 | done | FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic | 已执行 `pytest`、`compileall` |
| 容器化编排 | done | Dockerfile、Compose、Nginx、环境模板 | 已完成配置级检查 |

### Phase 1 / Foundation

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 枚举与数据库类型基线 | done | 统一枚举、JSON / enum DB 类型封装 | 已纳入后端测试 |
| 领域模型与 mixin | done | `users`、`departments`、`profiles`、`attachments`、`tasks`、`notification_*` 等模型 | 已执行模型与 metadata 测试 |
| Alembic 迁移 | done | `20260413_01_phase1_foundation.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 认证服务 | done | 管理员初始化、登录、refresh、当前用户解析 | 已执行服务测试 |
| 组织与档案服务 | done | 用户、部门、档案管理 | 已执行服务测试 |
| 附件与对象存储 | done | 本地对象存储适配器与附件服务 | 已执行上传 / 删除测试 |
| 任务与通知 | done | 任务创建 / 指派与消息入队骨架 | 已执行服务测试 |

#### 3. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 认证、用户、部门、档案、任务、附件 API | done | 标准 REST 接口与统一依赖注入 | 已执行 API 集成测试 |
| 开发态错误收口 | done | 数据库不可用时返回清晰 `503` 提示 | 已执行错误处理测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 会话层与路由守卫 | done | access token 内存态、HttpOnly refresh cookie 恢复、受保护路由 | 已执行单元测试 |
| 基础后台页面 | done | 仪表盘、部门页、档案页、任务页、附件上传 | 已执行 `type-check`、`build`、`lint` |
| 联调修复 | done | 修复开发代理 404、本地 / Compose 启动链路 | 已完成用户实际点击验证 |

### Phase 2 / Collaboration & Stats

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 枚举与协同模型 | done | `TaskActionType`、`CommentFormat`、`TaskLog`、`TaskComment` | 已执行模型与迁移相关测试 |
| Alembic 迁移 | done | `20260414_01_phase2_collaboration.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 状态机与审计 | done | 严格任务状态机、自动维护开始/完成时间、自动日志 | 已执行合法 / 非法流转测试 |
| 评论与活动流 | done | 评论、内部备注、评论附件、活动流聚合 | 已执行权限、附件与排序测试 |
| 统计查询 | done | 完成率、逾期率、状态分布、负载查询 | 已执行样例口径测试 |

#### 3. Worker 与异步提醒

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| ARQ Worker | done | `jobs.py`、`arq_worker.py`、`start-worker.sh` | 已执行 worker 单元测试 |
| 编排补齐 | done | Compose 新增 `worker` 服务 | 已完成配置级检查 |

#### 4. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 任务协同接口 | done | 状态流转、评论、活动流、统计接口 | 已执行 API 集成测试 |

#### 5. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 协同任务页 | done | 统计卡片、状态按钮、评论区、评论附件、活动时间线、负载概览 | 已执行 `test:unit`、`type-check`、`build`、`lint` |
| 用户基础验测 | done | 用户进行了简单测试并确认“看上去基本没有问题” | 已完成阶段性文档收口 |

### Phase 3 / HR Governance & Org Modeling

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| HR 治理枚举与模型 | done | `positions`、`profile_positions`、`reporting_lines`、`profile_field_*`、`employment_events`、`delegations` | 已执行模型持久化测试 |
| Alembic 迁移 | done | `20260415_01_phase3_hr_governance.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 组织关系与字段权限 | done | `OrganizationRelationService`、`ProfileFieldPolicyService`、扩展 `access_control.py` | 已执行权限矩阵与代理授权测试 |
| 生命周期与授权 | done | `HRLifecycleService`、`DelegationService`、重构 `ProfileService` | 已执行生命周期事件与状态联动测试 |

#### 3. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 档案治理接口 | done | `profiles` 子资源接口、`hr_governance` 路由 | 已执行 API 集成测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 档案治理工作台 | done | 多标签档案页、岗位 / 汇报线 / 生命周期 / 授权表单 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 5. 当前阶段闸门

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 用户手动验测 | done | 用户已按复现路径重新验证迁移与 Compose 启动链路 | 已完成自动化验证与用户手动验测 |

### Phase 4 / Workflow Engine & Messaging

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Workflow / Messaging 枚举与模型 | done | `task_templates`、`workflow_*`、`task_watchers`、`task_schedules`、`notification_receipts` | 已执行模型与 metadata 测试 |
| Alembic 迁移 | done | `20260416_01_phase4_workflow_messaging.py` | 已执行升级 / 回滚与约束回归测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 模板 / 审批 / 自动化服务 | done | `TaskTemplateService`、`WorkflowEngineService`、`TaskAutomationService`、`workflow_rule_resolver.py` | 已执行服务测试 |
| 消息中心与任务扩展 | done | `MessageCenterService`、`TaskService` watcher / board / gantt 扩展 | 已执行服务测试 |

#### 3. Worker 与 API

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Worker 调度与提醒 | done | 周期模板实例化、审批提醒扫描、ARQ cron 注册 | 已执行 worker 单元测试 |
| 模板 / 审批 / 消息 API | done | `task_templates`、`workflows`、`messages` 路由及 `tasks` 多视图 / watcher 接口 | 已执行 API 集成测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Workflow 工作台 | done | `TaskTemplatesView.vue`、`ApprovalsView.vue`、`MessagesView.vue` | 已执行前端单元测试 |
| 任务中心多视图 | done | `TasksView.vue` 扩展列表 / 看板 / 甘特图与关注人 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 5. 当前阶段闸门

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 用户手动验测 | done | 用户已确认 Phase 4 通过，可进入下一阶段 | 已完成自动化验证与用户手动验测 |

### Phase 5 / Knowledge, AI Router & Experience

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Knowledge / Push 模型与迁移 | done | `documents`、`document_embeddings`、`push_subscriptions`、`20260417_01_phase5_knowledge_push.py` | 已执行模型、metadata、迁移与配置测试 |
| 编排与数据库基线 | done | Compose PostgreSQL 切换到 `pgvector/pgvector:pg16`，补齐 OpenAI / VAPID 配置项 | 已完成配置级检查与测试覆盖 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 文档与检索服务 | done | `DocumentService`、`KnowledgeRetrievalService`、文档附件与 embedding 重建 | 已执行服务测试 |
| AI Router 与工具注册 | done | `ToolRegistryService`、`LLMRouterService`、`@系统` / `/` 路由编排 | 已执行服务与 API 测试 |
| Push 与通知渠道 | done | `BrowserPushService`、Web Push adapter、通知 adapter factory | 已执行服务、worker 与 API 测试 |

#### 3. Worker / API / 前端

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Worker 与 adapter | done | 文档 embedding job、通知投递分发、Web Push 发送 | 已执行 worker 单元测试 |
| API 层 | done | `documents`、`knowledge`、`ai_router`、`push_subscriptions` 路由与 schema | 已执行 API 集成测试 |
| 前端工作台 | done | 知识库页、命令栏、Push 订阅卡片、PWA 基线 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 4. 阶段后续补丁

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 浏览器通知业务链路补齐 | done | 任务指派、转派、抄送、逾期提醒、审批提醒已接入 `WEB_PUSH`，并做订阅感知过滤 | 已执行后端与前端全量回归 |
| 用户管理入口补齐 | done | 新增 `/users` 工作台、侧边栏导航与前端测试 | 已执行前端全量验证 |
| 测试数据脚本 | done | `SampleDataService`、`python -m app.scripts.seed_sample_data`、可重复 demo 组织与账号 | 已执行服务测试并实际生成测试数据 |

## 用户验测补记

### Phase 1 验测补记

用户在点击“初始化管理员”和“登录”时，先后暴露出两类问题：

1. 前端开发代理缺失，导致请求命中前端开发服务器并返回 404。
2. 数据库未启动 / 连接不可用，导致后端抛出长链路超时异常。

对应修复已经落地：

- 增加 Vite 代理与开发态直连 fallback
- 补齐 `.env.example`、Compose 自动迁移与更明确的 `503` 错误提示

### Phase 2 验测补记

- 用户进行了简单功能测试，反馈“看上去基本上没有问题”。
- 因此当前 `memory-bank` 已按 **Phase 2 已完成** 的事实收口。

## 重构执行补记

### Step 2 / 总览模块

- 已新增部门能力字段 `departments.capabilities`，用于公告发布等能力控制。
- 已新增 `board_cards`、`board_card_archives`、`announcements`、`announcement_archives`。
- 已新增总览聚合接口、看板发布 / 归档、公告发布 / 撤下，以及待办 / 跟踪任务投影。
- 已重写 `HomeView.vue`，首页现在显示看板、公告、待办事项、任务跟踪和任务中心快捷入口。
- 已补齐后端 `pytest`、`compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 用户已确认 Step 2 通过，当前已作为 Step 3 的进入基线。

### Step 3 / 任务中心重构

- 已新增 `task_memos` 表、迁移、模型关系与 CRUD 服务。
- 已新增 `/api/v1/task-center` 与 `/api/v1/task-center/memos`，统一输出模板摘要、发布权限、待办、跟踪、历史与备忘。
- 已将模板管理与模板实例化权限从“仅管理角色”扩展为“管理角色 + 部门负责人 + 部门能力”。
- 已将前端 `TaskCenterView.vue` 重构为六标签工作台：任务模板、发布任务、待办事项、任务跟踪、历史任务、备忘。
- 已保留 `TasksView.vue` 的活动时间线、任务协同详情与负载概览，并作为任务跟踪详情区复用。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 用户已确认 Step 3 通过，因此当前重构基线已推进为 **Step 3 done / Step 4 start**。

### Step 4 / 汇报中心落地

- 已新增 `reports`、`report_routes` 表、迁移、模型关系与 API schema。
- 已新增 `/api/v1/report-center`、`/api/v1/report-center/reports` 与动作接口，支持发起、流转、退回、归档。
- 已新增 `ReportService`、`ReportCenterService`，支持逐级向上汇报、逐级向下传达、代理委托、可选挂接 workflow instance。
- 已将 `/reports` 页面升级为真正的汇报中心，支持待处理、我发起、历史归档、发起向上汇报、发起向下传达五个标签。
- 已通过通知总线把新汇报 / 新传达接入消息中心与浏览器推送链路。
- 已补齐 request id 中间件、统一 500 错误处理、`error_events` 错误事件落库，以及前端错误提示中的 request id 展示。
- 已定位真实根因为：`reports` / `report_routes` 在 ORM flush 时写入了枚举名（如 `UPWARD` / `IN_PROGRESS`），而 PostgreSQL check constraint 只接受小写枚举值（如 `upward` / `in_progress`）；现已仅在汇报领域切换为按 `enum.value` 持久化。
- 已新增回归测试，直接断言 report 领域枚举写库值为小写；同时保留 500 响应 request id 与 `error_events` 落库测试。
- 已在 Docker Compose + PostgreSQL 真环境中，用 `demo.engineer.a@example.com` 对“方舟”“高原”两条向上汇报目标完成复测，均返回 `201`。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 用户已确认 Step 4 通过；当前重构执行基线已推进为 **Step 4 done / Step 5 pending**。

### Step 5 / 档案管理 & 用户管理合并

- 已新增 `PeopleManagementService` 与 `/api/v1/people-management`、`/api/v1/people-management/{user_id}`，统一编排账号、档案、任职、生命周期与权限视图读模型。
- 已明确 Step 5 只新增聚合读接口；账号、档案、任职、汇报、生命周期、代理授权写链路继续复用既有 `/users` 与 `/profiles*` 接口，不引入新的聚合写接口与 schema 迁移。
- 已将前端 `PeopleManagementView.vue` 从 Users / Profiles tab 壳层升级为真正的统一人员工作台：左侧人员列表与筛选，右侧账号信息、档案信息、岗位 / 汇报、生命周期、权限视图多标签详情。
- 已在统一人员工作台内保留并接通关键管理动作：新建账号、补建档案、编辑账号、编辑档案、岗位目录维护、任职维护、汇报线维护、生命周期事件记录、代理授权创建 / 撤销。
- 已新增后端 service / API 回归测试，以及前端 `PeopleManagementView.spec.ts`，覆盖聚合读取、角色保护、详情标签切换、补建档案与统一写链路调用。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 全量回归。
- 用户已确认 Step 5 通过；当前重构执行基线已推进为 **Step 5 done / Step 6 start**。

### Step 6 / 消息中心联动与提醒收口

- 本轮目标是让总览、任务中心、汇报中心、公告与消息中心形成闭环，重点收口来源对象标识、用户级隔离、未读 / 未确认状态与来源回跳。
- 已复用现有 `notification_messages`、`notification_deliveries`、`notification_receipts`，未新增表结构；后端通过聚合读模型与统一来源 payload 完成来源模块、来源对象、来源回跳、未读 / 已确认状态输出。
- 已将消息中心后端严格收口为“当前用户自己的 inbox”，不再允许管理角色通过消息中心查看他人收件箱；同时把 `task` / `report` / `announcement` / `workflow` 的消息 payload 统一为可回跳协议。
- 已将前端 `MessagesView.vue` 升级为真正的消息工作台，补齐统计卡、未读 / 未确认 / 来源筛选、我的回执状态与“回到来源”入口；`HomeView.vue`、`TaskCenterView.vue`、`TasksView.vue`、`ReportsView.vue` 已补齐来源 query 的高亮 / 选中消费。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 全量回归。
- 当前状态：**Step 6 done / user accepted**；已作为 Step 7 的进入基线。

### Step 7 / 当前重构收口

- 本轮目标是把当前重构成果正式收口为可交接、可验证、可继续迭代的稳定基线。
- 本轮收口范围包括：推进 `memory-bank`、同步根 `README.md`、修正明显过时的子目录 README、执行后端 / 前端全量回归。
- 已完成根 `README.md`、`backend/README.md`、`frontend/README.md`、`infra/docker/README.md` 的当前基线同步，并把前端壳层中的阶段文案从旧的 Phase 5 / Knowledge 文案收口到 Step 7。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 全量回归。
- 用户已确认可以进入下一轮实现，因此 Step 7 已作为稳定基线收口完成。
- 当前状态：**Step 7 done / user accepted**。

### 工作流 E / 结构化任务模板与多步骤协作

- 已完成后端运行态模型与迁移：新增 `TaskTemplateInstance`、`TaskTemplateStepRun`、`tasks.template_instance_id`、`tasks.template_step_run_id`，并落地 `20260422_01_template_runtime.py`。
- 已完成服务层切换：`TaskTemplateService.instantiate_template()` 改为“创建实例 + 激活首批就绪步骤”；`TaskService` 在任务完成后回写步骤运行态并自动激活下游，支持 `single` / `fan_out` 与 `all` / `any` 汇聚语义。
- 已完成 API 协议扩展：模板步骤显式暴露 `assignment_mode` / `join_mode`；实例化接口返回实例快照；新增 `GET /task-templates/{template_id}/instances`。
- 已完成前端结构化设计器首版：支持步骤增删改、依赖选择、负责人规则、JSON 导入、实例快照展示，以及已有模板的结构化编辑。
- 已完成模板管理补丁：仅允许删除从未实例化过的模板；已有实例时允许元数据更新，但禁止步骤结构改写，并在前端锁定结构设计器，修复更新模板 `500`。
- 已完成工作台体验收口：总览页补齐看板 / 公告人工归档、任务中心快捷跳转与快捷入口卡片；消息中心已拆分出设置页承载 Push / PWA；任务中心主标签收口为待办 / 跟踪 / 发布 / 模板 / 备忘，历史任务并入跟踪视图；登录页不再预填默认管理员邮箱和密码。
- 已完成定向验证：后端 `pytest -q tests/test_services.py tests/test_api.py`、后端 `python -m compileall app tests`、前端 `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts tests/HomeView.spec.ts tests/TaskCenterView.spec.ts tests/LoginView.spec.ts tests/SettingsView.spec.ts tests/AppShell.spec.ts tests/Router.spec.ts`、前端 `npm run type-check`。
- 当前下一步：继续做前后端全量回归、云部署收口、模板 / 调度管理深化，以及岗位编辑器 / JSON 治理与生命周期事件联动。

### Phase 3 验测补记

- Phase 3 代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 用户在首次手动验测时发现 PostgreSQL 外键名超长，导致 `alembic upgrade head` 与 Compose backend 启动失败。
- 修复内容：
  1. 缩短 `profile_field_permissions` 的外键名，满足 PostgreSQL 63 字符限制
  2. 新增 metadata / Alembic identifier 长度回归测试
  3. 在真实 PostgreSQL、backend 容器和 Compose backend 服务路径上完成复测
- 用户已按原复现步骤重新验证，确认问题通过。

### Phase 4 验测补记

- Phase 4 代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 本阶段新增的关键能力包括：
  1. 任务模板与周期调度
  2. 轻量审批流引擎（串行 / 会签 / 或签 / 打回 / 驳回 / 代理审批）
  3. 消息中心与用户回执
  4. 任务中心列表 / 看板 / 甘特图多视图与 watcher
- 用户已确认 Phase 4 通过，因此当前文档状态已推进为 **Phase 4 done / Phase 5 next**。

### Phase 5 验测补记

- Phase 5 主体代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 本阶段新增的关键能力包括：
  1. Markdown 知识库与文档附件
  2. embedding 重建、RAG 检索与 `pgvector`
  3. `@系统` / `/` 路由与 Tool Calling
  4. 浏览器 Push 订阅、Web Push adapter 与 PWA 基线
- 用户在阶段后续使用中发现：
  1. 业务消息尚未完整接入浏览器推送
  2. 前端缺少用户管理入口
- 对应 follow-up 已完成：
  1. 补齐任务与审批相关 Web Push 业务链路，并改为订阅感知 delivery 创建
  2. 新增 `/users` 用户管理页与导航入口
  3. 新增测试组织 / demo 用户初始化脚本，便于后续测试
- 当前文档基线已按 **Phase 5 done** 收口，下一步等待用户确认后进入更深入的重构与测试。

## 当前可用能力

- 管理员初始化、登录、JWT access token + HttpOnly refresh cookie 会话
- 用户管理
- 部门树与组织范围查询
- 员工档案基础 CRUD（含 `custom_fields`）
- 多岗位 / 兼职 / 虚线汇报维护
- 档案字段级权限裁剪（self / leader / delegate / HR / admin）
- 生命周期事件：入职、转岗、晋升、奖惩、离职、返聘
- 代理授权创建、撤销与按时间窗生效
- 档案治理工作台
- 任务创建、重新指派、前置依赖建模
- 严格任务状态机
- 任务评论、内部备注、评论附件、活动时间线
- 任务完成率 / 逾期率 / 负载统计
- 任务模板、模板实例化与周期任务调度
- 审批流定义、审批实例、待办审批与代理审批
- 任务 watcher / 抄送
- 任务中心列表 / 看板 / 甘特图多视图
- 通知消息落库、ARQ 入队、adapter 分发、逾期提醒扫描与状态回写
- 消息中心收件箱、消息回执与浏览器推送订阅
- 文档知识库、文档附件、embedding 重建、RAG 检索
- `@系统` / `/` 命令入口与 Tool Calling
- PWA manifest / service worker 基线
- 用户管理工作台（`/users`）
- 测试组织 / demo 用户初始化脚本
- Compose 本地开发基线（postgres / redis / backend / worker / frontend / nginx）

## 当前明确缺口（非完成项）

| 方向 | 仍未实现或需继续深化的关键能力 | 当前判断 |
| --- | --- | --- |
| 注册与账号开通 | **邀请制注册**（创建未启用账号、预览链接、设置密码激活、撤销）已落地；**访客公开自助注册**与**审批式注册**仍未实现，需产品决策 | 邀请 done；公开 / 审批式待决策与实现 |
| HR 流程自动化 | 生命周期事件与任务模板 / 审批流**显式绑定 + worker 异步触发**已落地；**规则化默认映射**与**前端结构化配置入口**仍待补齐；字段权限可视化管理增强 | 后续增强 |
| 消息渠道深化 | 消息附件绑定、筛选与失败详情已落地（Stage 2 Phase 4）；真实 Email / WebSocket 对外发送接入、delivery 观测增强仍待深化 | 后续增强 |
| 工程质量 | 更细的重构、集成测试、E2E 扩面；**回滚演练**与 docker-gui 基线刷新 | 下一轮重点 |

## 当前规划焦点

Stage 2 周期（Phase 0–6 + IA A–F）已收口。当前建议优先级：

1. **Ubuntu 最小回滚路径演练**（补 Phase 6 遗留；git 回退 + systemd 重启 ± 迁移 rollback dry-run）
2. **工作流 E 与图引擎产品级统一**、模板 / 调度深化、全量回归扩面
3. **生命周期规则化默认映射 + 前端结构化配置入口**
4. **公开 / 审批式注册（若需要）与真实通知渠道适配**
5. **Playwright live / docker-gui 与发布 commit 同步重跑**（下次大版本前刷新基线）

## 重构执行补记

### Step 1 / 壳层导航重构

- 用户已确认 Step 1 通过。
- 本步骤已完成：
  1. 左侧导航按“通用模块 / 特殊模块”分组
  2. 主入口路由调整为 `/overview`、`/task-center`、`/reports`、`/people`
  3. 旧地址 `/dashboard`、`/tasks`、`/task-templates`、`/approvals`、`/users`、`/profiles` 已接入兼容跳转
  4. 新增 `TaskCenterView.vue` 与 `PeopleManagementView.vue` 两个聚合壳层，避免任务模板、用户页、档案页在重构早期失去入口
  5. `部门管理` 收紧为仅管理员可见，`人员管理` 对 `admin / hr` 可见
- 已完成验证：
  - 前端单元测试
  - 路由兼容跳转测试
  - `type-check`
  - `build`
  - `lint`
