# Project Filum 文档与实现对齐评估

**审查日期**: 2026-04-22  
**审查范围**: `memory-bank/`、根目录与子目录 `README`、后端关键路由 / 服务 / 模型 / 迁移、前端关键路由 / 视图 / 测试  
**审查方式**: 基于仓库当前代码、现有测试文件与文档交叉核对；本次未重新执行全量自动化命令
**后续修复状态**: 2026-04-22 已按本报告建议完成 `refactor-plan.md` 与 `progress.md` 的文档收口；本报告保留为修复前审查快照

## 1. 结论摘要

当前仓库的 `memory-bank` 主干文档与实际实现整体**高对齐**。`architecture.md`、`progress.md`、`implementation-plan.md`、根目录 `README.md`、`backend/README.md`、`frontend/README.md` 对当前基线的描述，和代码中的聚合路由、前端路由、通知总线、消息中心、人员工作台、汇报中心、知识库 / AI Router 等实现基本一致。

本次核对后，发现的主要问题集中在 **`memory-bank/refactor-plan.md` 仍残留部分提案态表述**，以及 **`memory-bank/progress.md` 的 Step 7 收口描述里混入了计划性措辞**。这两类问题更偏向文档漂移和表述含混，而不是实现缺口。

结论上可以把当前状态归类为：

- 主基线文档：已对齐
- 重构历史文档：局部漂移
- 已知缺口说明：已对齐，未发现把“目标态”误写成“已实现”的重大错误

## 2. 对齐项

### 2.1 项目阶段与交付状态已基本对齐

- `memory-bank/architecture.md`、`memory-bank/progress.md`、`memory-bank/implementation-plan.md`、根目录 `README.md` 都把当前状态描述为：Phase A 与 Phase 1-5 已完成，重构 Step 1-7 已实现，当前停在 Step 7 等待用户验测。
- 代码侧存在与之对应的实现入口：`backend/app/api/routes/overview.py`、`backend/app/api/routes/task_center.py`、`backend/app/api/routes/report_center.py`、`backend/app/api/routes/messages.py`、`backend/app/api/routes/people_management.py`。
- 前端路由也与当前信息架构一致：`frontend/src/router/index.ts` 已以 `/overview`、`/task-center`、`/reports`、`/messages`、`/people`、`/departments` 为主入口，并保留旧路由兼容跳转。
- 现有测试可作为回归证据：`frontend/tests/Router.spec.ts`、`frontend/tests/TaskCenterView.spec.ts`、`frontend/tests/PeopleManagementView.spec.ts`、`frontend/tests/MessagesView.spec.ts`。

### 2.2 任务中心、汇报中心、人员工作台、消息中心的聚合式实现已对齐

- 后端总路由 `backend/app/api/router.py` 已注册 `task-center`、`report-center`、`messages`、`overview`、`people-management` 等聚合入口。
- `backend/app/api/routes/report_center.py` 与 `frontend/src/router/index.ts` 共同证明：汇报中心当前对外页面入口是 `/reports`，后端聚合 API 入口是 `/api/v1/report-center`。
- `backend/app/api/routes/people_management.py` 与 `backend/app/services/people_management_service.py` 证明：人员工作台当前后端聚合入口是 `/api/v1/people-management`，聚合服务名是 `PeopleManagementService`。
- `frontend/tests/PeopleManagementView.spec.ts`、`frontend/tests/MessagesView.spec.ts`、`frontend/tests/TaskCenterView.spec.ts` 覆盖了这些工作台的关键页面行为。

### 2.3 通知总线与消息中心说明已对齐

- `backend/app/services/notification_service.py` 的实现与 `memory-bank/architecture.md` 中“通知总线链路”的描述一致：服务层写入 `notification_messages` 与 `notification_deliveries`，随后交由队列发布器异步投递。
- `backend/app/models/notification.py` 中的 `NotificationMessage`、`NotificationDelivery`、`NotificationReceipt` 与文档中的消息 / 投递 / 回执建模一致。
- `backend/app/services/message_center_service.py` 与 `backend/app/api/routes/messages.py` 证明：消息中心当前已经收口为当前用户自己的 inbox，支持来源聚合、回执状态、来源回跳。
- `frontend/tests/MessagesView.spec.ts` 进一步证明：前端已经消费来源回跳与确认回执能力。

### 2.4 已知缺口描述与当前实现一致

- `memory-bank/architecture.md`、`memory-bank/implementation-plan.md` 都把“消息附件”列为未实现缺口；代码侧也支持这一点：
  - `backend/app/core/enums.py` 中 `AttachmentTargetType` 目前只有 `task_comment`、`task`、`profile`、`document`，未包含消息对象。
  - `backend/app/api/routes/messages.py` 与 `backend/app/services/message_center_service.py` 的读模型也没有消息附件字段。
- 文档把 Email / WebSocket 的真实外部集成描述为“最小实现后的下一步”；代码也支持这个判断：
  - `backend/app/integrations/notifications/factory.py` 已注册 `EMAIL`、`WEBSOCKET`、`WEB_PUSH` 三类 adapter。
  - 但 `backend/app/integrations/notifications/email.py` 与 `backend/app/integrations/notifications/websocket.py` 当前仍是返回伪外部 ID 的最小实现。

## 3. 问题清单

### 3.1 中严重度 / 文档漂移

**问题**: `memory-bank/refactor-plan.md` 仍混有已经过时的提案态命名和路径，容易与当前实现产生冲突。  
**类型**: 文档漂移  
**影响**: 中。该文件位于 `memory-bank/`，仍可能被后续代理或开发者当作当前实现参考，进而误用旧服务名、旧 API 入口或旧页面命名。

**已确认的漂移点**

- 文件中仍出现 `PeopleAdminService`，而当前真实实现为 `backend/app/services/people_management_service.py` 中的 `PeopleManagementService`。
- 文件中仍以提案口径描述 `/reports/*`、`/people/*` 等接口 / 聚合方向；当前真实后端聚合入口分别是 `backend/app/api/routes/report_center.py` 的 `/report-center` 和 `backend/app/api/routes/people_management.py` 的 `/people-management`。
- 文件中仍写有“新建 `OverviewView.vue`，替换 `HomeView.vue`”的规划表述；当前前端实际是 `frontend/src/router/index.ts` 将 `/overview` 挂载到 `HomeView.vue`，并已由 `frontend/tests/Router.spec.ts` 覆盖兼容跳转。

**证据**

- 文档: `memory-bank/refactor-plan.md`
- 后端: `backend/app/api/routes/people_management.py`、`backend/app/services/people_management_service.py`、`backend/app/api/routes/report_center.py`
- 前端: `frontend/src/router/index.ts`、`frontend/tests/Router.spec.ts`

**建议动作**

- 给 `memory-bank/refactor-plan.md` 增加醒目的“历史规划文档”说明，并注明当前事实以 `architecture.md`、`progress.md`、`README.md` 为准；或
- 直接将仍保留提案语气的章节更新为“规划 -> 实现映射”形式，避免继续使用旧命名。

### 3.2 低严重度 / 表述含混

**问题**: `memory-bank/progress.md` 的 Step 7 段落同时使用了“已实现 / 等待验测”和“当前计划包含提交最终收口 commit”两种口径，容易让读者误判 Step 7 的完成边界。  
**类型**: 表述含混  
**影响**: 低。不会直接误导业务实现，但会影响对“当前是否已彻底收口”的判断。

**表现**

- `memory-bank/progress.md` 的总表将 Step 7 标记为 `in_review`。
- 同文件 Step 7 详情中写有“当前计划包含：推进 memory-bank、同步 README、修正明显过时的子目录 README、执行后端 / 前端全量回归、提交最终收口 commit”。
- `memory-bank/implementation-plan.md` 又明确写明“当前停在 Step 7，等待用户手动验测，不进入新的功能范围”。

**证据**

- 文档: `memory-bank/progress.md`、`memory-bank/implementation-plan.md`

**建议动作**

- 将 Step 7 详情中的“当前计划包含”改为“本轮已完成项 / 待用户验测项”；
- 如果确实需要记录收口 commit，建议只在已经存在可核对提交号时再写入，否则去掉这类不可在仓库正文中直接验证的描述。

## 4. 建议修复顺序

1. 先修 `memory-bank/refactor-plan.md` 的历史提案残留，避免后续继续把旧命名当成当前实现。
2. 再修 `memory-bank/progress.md` 中 Step 7 的表述，把“计划态”与“已完成待验测态”明确分开。
3. 继续保持 `architecture.md`、`progress.md`、根目录 `README.md` 作为当前实现的主入口，避免把 `refactor-plan.md` 这种历史文档当成行为事实来源。

## 5. 证据索引

### 5.1 文档

- `memory-bank/architecture.md`
- `memory-bank/design-document.md`
- `memory-bank/progress.md`
- `memory-bank/implementation-plan.md`
- `memory-bank/refactor-plan.md`
- `README.md`
- `backend/README.md`
- `frontend/README.md`
- `infra/docker/README.md`

### 5.2 后端实现

- `backend/app/api/router.py`
- `backend/app/api/routes/overview.py`
- `backend/app/api/routes/report_center.py`
- `backend/app/api/routes/messages.py`
- `backend/app/api/routes/people_management.py`
- `backend/app/services/notification_service.py`
- `backend/app/services/message_center_service.py`
- `backend/app/services/people_management_service.py`
- `backend/app/models/notification.py`
- `backend/app/schemas/messages.py`
- `backend/app/core/enums.py`
- `backend/app/integrations/notifications/factory.py`
- `backend/app/integrations/notifications/email.py`
- `backend/app/integrations/notifications/websocket.py`

### 5.3 前端与测试证据

- `frontend/src/router/index.ts`
- `frontend/tests/Router.spec.ts`
- `frontend/tests/MessagesView.spec.ts`
- `frontend/tests/PeopleManagementView.spec.ts`
- `frontend/tests/TaskCenterView.spec.ts`
