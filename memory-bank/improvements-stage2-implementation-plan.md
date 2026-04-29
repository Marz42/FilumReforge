# Project Filum Stage 2 实施方案

## 0. 命名约定

本文件是当前这一轮后续重构与增强的 Stage 2 实施方案。

- `Stage 2` 指当前已交付基线之后的新实施周期，不等同于历史上已经完成的 `Phase 2 / Collaboration & Stats`
- 本文件内部保留 `Phase 0-6` 作为 Stage 2 周期内的执行阶段
- 从本文件开始，相关进度与架构同步统一使用 `Stage 2` 表述，避免与历史阶段命名冲突

## 1. 文档定位

本文件用于把 `improvments-phase2.md` 中的改进方向拆成可以逐步执行的 Stage 2 实施方案。目标不是重复描述改进意图，而是明确：

- 每个阶段要改什么
- 依赖哪些现有模块
- 需要补哪些测试
- 交付后如何验收

本方案默认遵循以下原则：

1. 保持模块化单体边界，不发起高风险整体重写。
2. 保留当前 `Task` + `TaskTemplateStepRun` 的渐进演进路线。
3. 每个阶段必须具备最小可验证出口。
4. 每个阶段完成后必须同步更新 `progress.md` 与 `architecture.md`。
5. 文档更新只做最小、可验证同步。

## 2. 总体推进顺序

建议按以下 Stage 2 阶段顺序推进：

1. Phase 0 / 基线冻结与阶段确认
2. Phase 1 / 前端体验收敛
3. Phase 2 / 模板工作台与工作流 E 治理
4. Phase 3 / 生命周期事件联动
5. Phase 4 / 消息中心深化
6. Phase 5 / 注册与账号开通
7. Phase 6 / 部署演练与全量回归

串行约束：

- Phase 2 完成后再进入 Phase 3
- Phase 1 与 Phase 2 可以局部并行，但推荐先完成 Phase 1 的可见体验收敛
- Phase 6 依赖本轮纳入上线范围的功能全部完成

## 3. Phase 0 / 基线冻结与阶段确认

### 3.1 目标

在开始连续编码前，先固定 Stage 2 范围、设计决策与验证命令，避免实施过程中阶段边界漂移。

### 3.2 具体步骤

1. 以 `improvments-phase2.md` 为目标来源，确认 Phase 1-6 的阶段边界。
2. 以 `implementation-plan.md` 为主基线，确认不与当前工作流 E 主线冲突。
3. 固定本轮关键决策：
   - 任务中心待办 tab 先弱化，不立即删除
   - 模板版本方案优先递增整数
   - 注册能力优先邀请制
   - 生命周期联动采用异步触发 + 可观测失败
4. 固定每个阶段的验证命令与验收口径。
5. 约定每个阶段完成后必须先更新 `progress.md` 与 `architecture.md`，再进入下一阶段。

### 3.3 相关文件

- `memory-bank/improvments-phase2.md`
- `memory-bank/improvements-stage2-implementation-plan.md`
- `memory-bank/implementation-plan.md`
- `memory-bank/workflow-refactor.md`

### 3.4 测试

1. 文档一致性检查：核对三份文档对阶段与边界的描述是否一致。
2. 路径检查：确认每个阶段都写明至少一条自动化验证命令。

### 3.5 验收内容

- 本文件形成稳定的 Stage 2 基线版本
- 后续实现代理可直接按阶段推进，不需要再次重构计划

## 4. Phase 1 / 前端体验收敛

### 4.1 目标

优先解决首页和任务中心的信息层级、入口职责和空状态占位问题，让用户第一眼看到的是“当前要处理什么”。

### 4.2 具体步骤

#### Step 1 / 首页首屏重排

1. 调整 `frontend/src/views/HomeView.vue` 的版面顺序：
   - 统计卡置顶
   - 快捷入口前置
   - 看板与公告放到统计层之后
   - 明细列表区保留在后段
2. 将首页统计卡“待办事项”改为“我的待办”，与下方明细列表区分语义。
3. 保持首页到任务中心的深链跳转能力，待办和跟踪都使用明确 tab 跳转。

测试：

- `npm run test:unit -- --run tests/HomeView.spec.ts`
- `npm run type-check`

验收内容：

- 首页首屏最先显示任务摘要卡
- 首页统计卡与下方列表不再重名
- 从首页点击摘要卡可正确进入任务中心目标 tab

#### Step 2 / 空状态压缩

1. 压缩首页看板、公告、待办、跟踪四个板块的空状态高度。
2. 不改变已有数据态展示逻辑，只优化无数据时的占位面积。

测试：

- `npm run test:unit -- --run tests/HomeView.spec.ts`
- `npm run type-check`

验收内容：

- 空状态不再占据主要屏幕面积
- 数据态展示不回退

#### Step 3 / 任务中心入口职责收敛

1. 调整 `frontend/src/views/TaskCenterView.vue` 的默认 tab 为“任务跟踪”。
2. 待办 tab 保留，但下沉为次优先级入口，不再作为默认工作区。
3. 统计卡从“待办 / 跟踪 / 历史 / 模板”调整为“我的待办 / 跟踪任务 / 任务模板 / 我的备忘”。
4. 更新任务中心标题文案，明确当前工作台优先服务“跟踪、发布、模板、备忘”，待办保留为快速处理入口。

测试：

- `npm run test:unit -- --run tests/TaskCenterView.spec.ts`
- `npm run type-check`

验收内容：

- 默认进入任务中心时看到的是跟踪视图
- 待办 tab 仍可显式进入
- 统计卡口径与 tab 语义一致

#### Step 4 / 首页与任务中心联动回归

1. 检查首页摘要卡、快捷入口、任务中心默认 tab 与显式 tab 之间的跳转一致性。
2. 统一首页与任务中心的空状态和入口语义。

测试：

- `npm run test:unit -- --run tests/HomeView.spec.ts tests/TaskCenterView.spec.ts`
- `npm run type-check`
- `npm run build`

验收内容：

- 首页和任务中心之间的跳转路径稳定
- Stage 2 Phase 1 改动仅限前端，不引入后端 API 变更

### 4.3 相关文件

- `frontend/src/views/HomeView.vue`
- `frontend/src/views/TaskCenterView.vue`
- `frontend/tests/HomeView.spec.ts`
- `frontend/tests/TaskCenterView.spec.ts`

## 5. Phase 2 / 模板工作台与工作流 E 治理

### 5.1 目标

把当前模板能力从“已可用”推进到“可管理、可验证、可持续回归”的状态。

### 5.2 具体步骤

#### Step 1 / 结构化设计器前端校验补齐

1. 为 `frontend/src/views/TaskTemplatesView.vue` 增加以下校验：
   - `step_key` 不可重复
   - 正常流转路径无环
   - 依赖无孤岛
   - `join_mode` / `assignment_mode` 组合合法
   - 空 `assignee_rule` 阻止提交
2. 吸收 `workflow-refactor.md` 的邻接表表达，把流转去向显式化，而不是继续埋在散乱 JSON 中。

测试：

- `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`
- `npm run type-check`

验收内容：

- 非法拓扑配置无法提交
- 错误提示对业务用户可理解

#### Step 2 / 模板版本与锁定提示

1. 在 `backend/app/models/task_workflow.py` 和相关 schema/service 中补模板版本字段或版本语义。
2. 对已有实例的模板给出结构锁定提示，默认引导新建版本。

测试：

- `pytest -q backend/tests/test_models.py backend/tests/test_services.py backend/tests/test_api.py`
- `python -m compileall app tests`

验收内容：

- 模板版本信息可查询、可展示
- 已实例化模板不能无提示地直接改结构

#### Step 3 / 调度治理与实例运行态增强

1. 补模板调度的启停、最近执行结果、下次执行时间和失败原因。
2. 增强实例运行态展示：阻塞依赖、完成进度、历史迭代。
3. 为 fan-out / join 激活补幂等保护和重复激活约束。

测试：

- `pytest -q backend/tests/test_models.py backend/tests/test_services.py backend/tests/test_api.py backend/tests/test_workers.py`
- `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`
- `npm run type-check`
- `npm run build`

验收内容：

- 调度状态与最近执行结果可见
- 实例运行态能解释当前阻塞与历史重跑
- 并发推进不会重复激活下游步骤

## 6. Phase 3 / 生命周期事件联动

### 6.1 目标

把生命周期事件从“记录行为”升级为“事件驱动模板/审批”的入口。

### 6.2 具体步骤

1. 在 `backend/app/services/hr_lifecycle_service.py` 中补事件驱动模板实例或审批流的服务编排。
2. 为事件增加触发状态、触发时间、失败记录与幂等保护。
3. 优先覆盖入职、离职、转岗三类事件。
4. 失败采用异步重试和错误记录，不阻塞事件主事务。

测试：

- `pytest -q backend/tests/test_services.py backend/tests/test_api.py`
- `pytest -q backend/tests/test_migrations.py`

验收内容：

- 关键事件可自动生成模板实例或审批流
- 重复提交不会生成重复运行实例
- 失败可在系统中追踪

## 7. Phase 4 / 消息中心深化

### 7.1 目标

补齐消息附件与更细粒度观测，让消息中心从“通知箱”升级为“可追踪的通知中台”。

### 7.2 具体步骤

1. 为消息模型补附件关联，不再只依赖 payload 嵌入。
2. 为消息中心补模块、时间、回执、渠道筛选。
3. 扩展投递失败、重试、过期订阅等状态展示。
4. 保持当前“先落库再异步投递”模式，增强 outbox / retry 可观测性。

测试：

- `pytest -q backend/tests/test_models.py backend/tests/test_services.py backend/tests/test_api.py backend/tests/test_workers.py`
- `npm run test:unit -- --run tests/MessagesView.spec.ts`
- `npm run type-check`

验收内容：

- 消息可展示附件
- 失败与重试状态可见
- 筛选器能支撑日常使用

## 8. Phase 5 / 注册与账号开通

### 8.1 目标

优先落邀请制注册，补齐当前“只能管理员建用户”的边界缺口。

### 8.2 具体步骤

1. 为用户与认证模型补邀请 token、有效期、注册状态等字段。
2. 增加邀请生成、校验、注册、激活、撤销与过期处理服务。
3. 扩展登录页与认证 store，支持邀请链路打开后的注册流程。

测试：

- `pytest -q backend/tests/test_services.py backend/tests/test_api.py backend/tests/test_settings.py`
- `npm run test:unit -- --run tests/LoginView.spec.ts tests/AuthStore.spec.ts`
- `npm run type-check`

验收内容：

- 管理员可生成邀请链接
- 用户可通过有效邀请完成注册并登录
- 过期、撤销、重复邮箱与越权路径都被正确阻止

## 9. Phase 6 / 部署演练与全量回归

### 9.1 目标

把已存在的生产产物从“文件齐备”推进到“上线流程真实验证过”。

### 9.2 具体步骤

1. 执行根目录 `scripts/check-release.sh`。
2. 按 `memory-bank/deployment-runbook-ubuntu-2404.md` 做一次完整部署演练。
3. 固化回滚步骤与最小恢复路径。
4. 同步收口 README、architecture、progress 中与本轮事实相关的描述。
5. 在不偏离部署主目标的前提下，允许纳入发布前阻塞的小范围补丁收口，例如账号开通链路的状态语义澄清、未建档账号管理动作补齐；此类补丁仍需补测试并同步文档。

测试：

- `bash scripts/check-release.sh`
- `pytest -q`
- `python -m compileall app tests`
- `npm run test:unit -- --run`
- `npm run type-check`
- `npm run build`

验收内容：

- 部署脚本可执行
- 健康检查通过
- 核心工作台可访问
- 文档与实际发布路径一致

## 10. 本文件结论

本轮实施的重点不是继续横向堆功能，而是先把首页、任务中心、模板系统、生命周期联动与消息中心做出稳定、可验收的收口路径。建议先完成 Phase 1 与 Phase 2，再进入跨模块业务闭环。

从 Stage 2 开始，每个阶段结束都必须完成两项文档动作：

- 更新 `memory-bank/architecture.md`，记录当前实现事实、受影响模块职责与结构变化
- 更新 `memory-bank/progress.md`，记录阶段状态、验证命令与验收结论
