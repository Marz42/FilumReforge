# UI 重构实施规格 v2（前端）

**状态**：已交付（Phase A–F，2026-05）  
**依据**：[`handbooks/user-manual.md`](../handbooks/user-manual.md) v1.1（与当前界面对齐）  
**上位规划**：[`ui-information-architecture-plan.md`](./ui-information-architecture-plan.md)（本文件为其 v2 细化版，取代原 §3 分期表的粗粒度描述）  
**事实来源**：[`frontend/src/router/index.ts`](../../frontend/src/router/index.ts)、各 `views/`、`AppShell.vue`、Playwright E2E

---

## 1. 目标与原则

### 1.1 北向目标（North Star）

| 区域 | 目标形态 |
| --- | --- |
| **侧栏** | 只承载「业务模块」一级入口；消息不再占主导航 |
| **顶栏** | AI 命令 + 角色信息 + **铃铛通知** + **最近截止倒计时** + 退出 |
| **总览** | Dashboard 小组件化，吸纳消息预览/待办/公告白板，**不**与任务中心合并 |
| **任务中心** | Quick Chips 过滤 + Master-Detail；List/Board/Gantt 为视图切换；模板/备忘迁出主视窗 |
| **汇报中心** | 邮件客户端式 Master-Detail；单一「撰写汇报」抽屉，收件人推断方向 |
| **设置** | 左子导航：个人资料 / 安全与密码 / 通知偏好 |
| **人员/部门** | 宽抽屉 + 锚点导航；部门树 + 详情分栏 |

### 1.2 实施原则

1. **分阶段交付**：A→F 顺序，每阶段可独立验收、可回滚。
2. **URL 兼容**：旧 query（如 `?tab=tracking`）保留 redirect 或映射，E2E 逐步迁移而非一次性断裂。
3. **testid 优先**：凡 Playwright 依赖的锚点变更须同步 E2E；新增交互一律带 `data-testid`。
4. **后端最小增量**：优先复用现有 API；仅 UX 必需时新增端点（如自助改密）。
5. **不合并领域**：总览 ≠ 任务中心；消息降级为壳层组件但保留 `/messages` 深链。

### 1.3 非目标

- 不改变任务/汇报/图引擎领域模型与核心 API 契约（除明确列出的增量）。
- 不与工作流图引擎 Phase 合并发布。
- 知识库 IA 大改（user-manual §6 无强制批注，维持现状）。
- 部门树拖拽排序（Phase E 仅树形展示 + 选中详情，拖拽列为后续可选）。

---

## 2. 现状与目标对照

### 2.1 路由与壳层（现状）

```
/login
/  → AppShell
  ├── /overview          HomeView
  ├── /task-center       TaskCenterView（4 Tab：inbox/tracking/memos/templates）
  ├── /knowledge-base    KnowledgeBaseView
  ├── /reports           ReportsView（3 Tab + 两步发起弹窗）
  ├── /messages          MessagesView（侧栏一级入口）
  ├── /settings          SettingsView（仅推送/PWA）
  ├── /people            PeopleManagementView（5 Tab 详情）
  └── /departments       DepartmentsView（表格）
```

### 2.2 目标路由（增量）

| 路径 | 说明 |
| --- | --- |
| `/task-templates` | **恢复为独立路由**（现 redirect 到 task-center?tab=templates） |
| `/messages` | **保留**；侧栏移除，由顶栏铃铛 Drawer 为主入口 |
| `/settings/:section?` | 可选 section：`profile` \| `security` \| `notifications`（默认 profile 或 notifications） |
| `/task-center` | query 迁移：`filter=inbox\|tracking\|history`，`view=list\|board\|gantt`，`selected=<id>` |
| `/reports` | query 迁移：`filter=pending\|initiated\|history`，`selected=<id>`，`compose=1` 打开撰写抽屉 |

### 2.3 组件目录（目标结构）

建议在 `frontend/src/components/` 下新增（实施时按需拆分）：

```
shell/
  AppHeader.vue              # 从 AppShell 抽出：铃铛、倒计时、用户菜单
  NotificationDrawer.vue     # 消息列表 + 未读角标
  DeadlineCountdown.vue      # 最近截止任务倒计时
  GlobalMemoFloat.vue        # 全局备忘浮窗
login/
  LoginForm.vue              # 场景 A
  InviteActivateCard.vue     # 场景 B
  BootstrapWizard.vue        # 场景 C
overview/
  OverviewMessageWidget.vue
  OverviewAnnouncementBoard.vue
  OverviewTodoWidget.vue
  OverviewTaskActionDrawer.vue
tasks/
  TaskFilterChips.vue
  TaskViewToggle.vue
  TaskMasterDetailLayout.vue # 包装 TasksView 或逐步内联
reports/
  ReportMasterDetailLayout.vue
  ReportComposeDrawer.vue
settings/
  SettingsLayout.vue         # 左子导航 + router-view
  ProfileSection.vue
  SecuritySection.vue
  NotificationsSection.vue   # 迁移 PushSubscriptionCard
people/
  PeopleDetailDrawer.vue
  PeopleAnchorNav.vue
departments/
  DepartmentTreePanel.vue
  DepartmentDetailPanel.vue
```

---

## 3. 分期总览

| 阶段 | 名称 | 范围 | 依赖 |
| --- | --- | --- | --- |
| **A** | 登录与设置基线 | 三场景登录、密码错误提示、设置三分栏、改密 | 可选：`POST /auth/change-password` |
| **B** | 壳层与消息降级 | AppHeader、铃铛 Drawer、侧栏去消息、URL 兼容 | A（无硬依赖，可并行） |
| **C** | 任务中心重构 | Chips + Master-Detail + 视图切换；模板/备忘迁出 | B（全局备忘浮窗可放 B 末或 C 初） |
| **D** | 汇报中心重构 | Master-Detail + 撰写抽屉 | — |
| **E** | 组织管理 | 人员宽抽屉 + 部门树 | — |
| **F** | 总览 Dashboard | 三小组件 + 顶栏倒计时 + 内联处理抽屉 | B、C、D（待办/汇报数据源） |

**推荐实施顺序**：A → B → C → D → E → F（F 依赖多模块数据组件，放最后 polish）。

---

## 4. Phase A — 登录与设置基线

### 4.1 范围

- 修复密码校验失败时的**空错误提示**（登录、邀请激活、初始化、bootstrap、人员管理创建/重置密码等所有写密码路径）。
- 登录页三场景分流（A/B/C）。
- 设置页左子导航 + 安全与密码（自助改密）。

### 4.2 步骤

#### A.1 密码错误提示统一

| 步骤 | 动作 | 文件/位置 |
| --- | --- | --- |
| A.1.1 | 阅读 `backend/app/core/password_policy.py`，整理规则文案（长度、大小写、数字等） | 后端只读 |
| A.1.2 | 新增 `frontend/src/utils/passwordPolicy.ts`：`validatePasswordClient(value)` 返回 `{ valid, reasons: string[] }`；与后端规则对齐 | 新文件 |
| A.1.3 | 新增 `frontend/src/utils/formErrors.ts`：`extractValidationDetail(error)` — 解析 FastAPI 422 `detail[]` 数组，拼接字段级消息 | 新文件 |
| A.1.4 | 扩展 `getErrorMessage`：422 时优先 `detail[].msg`；空字符串 fallback 为「密码不符合安全策略，请检查长度、大小写与数字要求」 | `utils/errors.ts` |
| A.1.5 | `LoginView.vue`：邀请/bootstrap 表单提交前客户端预检；`ElMessage.error` 展示具体原因列表 | `views/LoginView.vue` |
| A.1.6 | `PeopleManagementView.vue`：创建账号/重置密码同样接入 | `views/PeopleManagementView.vue` |
| A.1.7 | 单元测试（可选）：`passwordPolicy.ts` 边界用例 | `frontend/src/utils/passwordPolicy.test.ts` |

**验收**：故意输入 `123456` 等弱密码，界面必须显示**非空**、**可读**的中文原因；网络 422 同样展示服务端 detail。

#### A.2 登录三场景

| 场景 | 触发条件 | UI 行为 |
| --- | --- | --- |
| **A 正常** | 无 `invite` query，且 `/auth/bootstrap-status`（或现有等价检测）表明已有管理员 | 全屏居中登录卡片：邮箱 + 密码 + 登录按钮；**底部灰色小字**：「本系统采用邀请制，请联系 HR 获取账号」 |
| **B 邀请激活** | URL 含 `?invite=<token>` | **全屏**「欢迎加入，请设置密码」卡片；隐藏普通登录 Tab/链接；预填邮箱（来自 token 校验接口） |
| **C 系统初始化** | 后端返回空库需 bootstrap | **全屏**多步向导（邮箱 → 密码 → 姓名/员工编号 → 提交）；隐藏 A/B 其他入口 |

| 步骤 | 动作 |
| --- | --- |
| A.2.1 | 拆分 `LoginView.vue` 为容器 + `LoginForm` / `InviteActivateCard` / `BootstrapWizard` |
| A.2.2 | `onMounted`：读 `route.query.invite` → 场景 B；否则调 bootstrap 检测 → 场景 C 或 A |
| A.2.3 | 移除或隐藏现有「标签页切换」式三合一 UI（初始化管理员 Tab 不再与登录并列） |
| A.2.4 | 保留 `data-testid="login-page"`、`login-email`、`login-password`、`login-submit` |
| A.2.5 | 新增 `data-testid="login-invite-activate"`、`bootstrap-wizard` |

**验收**：三种 URL/后端状态下仅出现对应全屏 UI；E2E `login.spec.ts` 仍可通过场景 A 路径登录。

#### A.3 设置页三分栏

| 步骤 | 动作 |
| --- | --- |
| A.3.1 | 新建 `SettingsLayout.vue`：左侧 `el-menu` 三项 — 个人资料、安全与密码、通知偏好 |
| A.3.2 | 子路由或 query section：`/settings/profile`、`/settings/security`、`/settings/notifications` |
| A.3.3 | **个人资料**：展示当前用户姓名、邮箱、角色（只读，数据来自 `authStore.user` / `GET /auth/me`） |
| A.3.4 | **安全与密码**：当前密码、新密码、确认新密码；提交调用改密 API |
| A.3.5 | **通知偏好**：迁移现有 `PushSubscriptionCard.vue` 内容 |
| A.3.6 | `SettingsView.vue` 瘦身为 layout 入口或删除并由 router 直接指向 layout |

**后端依赖（A.3.4）**：

若尚无自助改密端点，新增：

```
POST /auth/change-password
Body: { current_password, new_password }
Response: 204 或 UserRead
```

权限：已登录用户仅能改自己的密码；校验 `validate_password_strength` + 当前密码正确。

**testid**：`settings-layout`、`settings-nav-security`、`settings-change-password-form`、`settings-new-password`、`settings-submit-password`。

**验收**：设置页三项可切换；改密成功后可登出并用新密码登录；推送订阅功能与重构前一致。

### 4.3 Phase A 出口清单

- [x] 弱密码错误提示非空（客户端 + 服务端）
- [x] 登录三场景 UI 分流
- [x] 设置三分栏 + 改密（含后端端点）
- [x] `login.spec.ts`、`settings.spec.ts` 绿；`user-manual.md` §3、§9 待审阅后同步

---

## 5. Phase B — 壳层与消息降级

### 5.1 范围

- 从 `AppShell.vue` 抽出顶栏能力。
- 消息中心从侧栏移除，改为铃铛 + 右侧 Drawer。
- 保留 `/messages` 全页路由（深链、E2E、「查看全部」链接）。

### 5.2 步骤

#### B.1 AppHeader 抽取

| 步骤 | 动作 |
| --- | --- |
| B.1.1 | 新建 `components/shell/AppHeader.vue` |
| B.1.2 | 迁入：CommandBar（或保持其位置）、当前用户/角色、退出登录 |
| B.1.3 | 预留右侧插槽：`notification-bell`、`deadline-countdown`（F 阶段实现 countdown，本阶段可占位） |
| B.1.4 | `AppShell.vue` 模板改为：`<AppHeader />` + 侧栏 + `<router-view />` |

#### B.2 NotificationDrawer

| 步骤 | 动作 |
| --- | --- |
| B.2.1 | 新建 `NotificationDrawer.vue`，复用 `MessagesView` 的列表/详情逻辑（抽 composable `useMessagesInbox()`） |
| B.2.2 | 顶栏铃铛：`el-badge` 显示未读数；点击 `el-drawer` 从右侧滑出，宽度 ~480px |
| B.2.3 | Drawer 内：精简筛选（默认「未读 + 全部来源」）；列表项点击 → 展开详情或 **直接跳转** 到任务/汇报（与「回到来源」一致） |
| B.2.4 | Drawer 底部链接：「查看全部消息」→ `router.push('/messages')` |
| B.2.5 | 轮询或现有 store：登录后拉取未读计数（复用 messages API） |

**从侧栏移除**：

```typescript
// AppShell.vue — generalNavigationItems 删除 messages 项
// 保留 route /messages 与 MessagesView.vue
```

#### B.3 URL 与深链

| 步骤 | 动作 |
| --- | --- |
| B.3.1 | 外部通知 payload 若指向 `/messages?id=`，保持兼容 |
| B.3.2 | 可选：`/messages?drawer=1` 在 AppShell 层自动打开铃铛 Drawer 并选中消息（便于从总览 widget 链入） |

**testid**：`header-notification-bell`、`notification-drawer`、`notification-drawer-item`、`notification-view-all`。

**验收**：

- 侧栏无「消息中心」；铃铛可见，未读角标正确。
- Drawer 可读消息、跳转来源、进全页 `/messages`。
- 管理员/员工 E2E §B 导航截图需更新预期菜单项。

### 5.3 Phase B 出口清单

- [x] AppHeader + NotificationDrawer 上线
- [x] 侧栏导航与 `user-manual.md` §1.2 一致（无消息项）
- [x] E2E `shell.spec.ts`；docker-gui 菜单仍通过侧栏项计数间接覆盖

---

## 6. Phase C — 任务中心重构

### 6.1 范围

- 取消 4 Tab（inbox / tracking / memos / templates）。
- Quick Chips + Master-Detail 统一布局。
- List / Board / Gantt 右上角视图切换。
- **任务模板** → 独立路由 `/task-templates`（侧栏或任务中心页头齿轮菜单，HR/管理员可见）。
- **个人备忘** → 全局浮窗 `GlobalMemoFloat.vue`（壳层挂载，任意页可用）。

### 6.2 目标布局（线框）

```
┌─────────────────────────────────────────────────────────────────┐
│ 任务中心                    [建立任务]  [⚙模板管理]  List|Board|Gantt │
├─────────────────────────────────────────────────────────────────┤
│ [需要我处理的] [我参与的/跟踪] [已完成/历史]     ← Quick Chips          │
├──────────────────┬──────────────────────────────────────────────┤
│ 任务列表 (~35%)   │  任务协同详情 (~65%)                            │
│ 可排序/搜索       │  （现有 TasksView 右侧面板逻辑）                  │
└──────────────────┴──────────────────────────────────────────────┘

全局右下角：备忘便签浮动按钮 → 展开备忘面板
```

### 6.3 步骤

#### C.1 路由与 query 迁移

| 旧 URL | 新 URL | 说明 |
| --- | --- | --- |
| `?tab=inbox` | `?filter=inbox` | 默认 filter |
| `?tab=tracking` | `?filter=tracking` | |
| `?tab=history`（若在 tracking 内嵌） | `?filter=history` | 原 history 表纳入 history filter |
| `?tab=memos` | — | 改为打开 GlobalMemoFloat |
| `?tab=templates` | `/task-templates` | 301 式 redirect |
| `?selected=<id>` | 保留 | 选中任务 |

| 步骤 | 动作 |
| --- | --- |
| C.1.1 | `TaskCenterView.vue` 删除 `el-tabs`；引入 `TaskFilterChips`、`TaskViewToggle` |
| C.1.2 | `filter` 驱动数据源：`inbox` → inbox API；`tracking` → tracking 列表；`history` → history API |
| C.1.3 | `view` 驱动 `TasksView` 内 list/board/gantt（已有能力，仅移动切换按钮到页头右上） |
| C.1.4 | `router/index.ts`：`task-templates` 指向 `TaskTemplatesView.vue`；`meta.roles` 按现模板权限 |
| C.1.5 | `LEGACY_TAB_MAP` 保留 6 个月兼容：`tab=inbox` → `filter=inbox` |

#### C.2 Master-Detail 统一

| 步骤 | 动作 |
| --- | --- |
| C.2.1 | inbox 行点击：右侧加载详情（现多需先切 tracking；改为 inbox 也可直接 detail） |
| C.2.2 | 左列统一为 `TaskMasterDetailLayout`：列表选中态、`selected` query 同步 |
| C.2.3 | 移除 TaskCenterView 内独立的 inbox/tracking **双表** + 下方再嵌 TasksView 的割裂结构；tracking 与 inbox 差异仅在 API 与列配置 |
| C.2.4 | 「建立任务」保留页头 Drawer；testid 不变 |

#### C.3 备忘全局化

| 步骤 | 动作 |
| --- | --- |
| C.3.1 | `GlobalMemoFloat.vue` 挂到 `AppShell.vue`（`v-if="authStore.isAuthenticated"`） |
| C.3.2 | 迁移 `TaskCenterView` 备忘 CRUD 逻辑到 composable `useTaskMemos()` |
| C.3.3 | UI：右下角 FAB → 展开卡片列表 + 编辑；支持置顶、关联任务 |
| C.3.4 | testid：`global-memo-fab`、`global-memo-panel` |

#### C.4 模板独立化

| 步骤 | 动作 |
| --- | --- |
| C.4.1 | 侧栏增加「任务模板」**或** 任务中心页头「模板管理」链接（二选一，建议侧栏「特殊」组下仅 admin/hr，与 user-manual 一致） |
| C.4.2 | `TaskTemplatesView.vue` 从 TaskCenterView 嵌套改为全页 |
| C.4.3 | 旧 `/task-center?tab=templates` redirect 到新路由 |

**testid 变更**：

| 保留 | 新增 | 废弃 |
| --- | --- | --- |
| `task-center-view`, `task-center-create-task`, `tasks-detail-panel` | `task-filter-inbox`, `task-filter-tracking`, `task-filter-history`, `task-view-list`, `task-view-board`, `task-view-gantt` | `task-center-tab-*` |

**验收**：

- 三 filter 切换无全页 Tab；选中任务 URL 含 `selected=`。
- Board/Gantt 与 List 展示同一 filter 数据集。
- 备忘任意页可开；模板独立路由可实例化。
- E2E C1 链路（建任务 → tracking → 详情 → 附件）更新 query 后仍绿。

### 6.4 Phase C 出口清单

- [x] TaskCenter Master-Detail + Chips + View Toggle
- [x] GlobalMemoFloat + `/task-templates` 路由
- [x] 旧 tab query redirect 文档化
- [x] `task-center.spec.ts` + docker-gui C1 更新

---

## 7. Phase D — 汇报中心重构

### 7.1 范围

- 邮件客户端式 Master-Detail（左列表、右阅读区）。
- 单一「撰写汇报」按钮 + 写邮件式 Drawer（收件人下拉推断向上/向下）。
- 取消「先选类型再填表」两步弹窗。

### 7.2 目标布局

```
┌─────────────────────────────────────────────────────────────────┐
│ 汇报中心     待处理 n · 我发起 n          [撰写汇报]                  │
├─────────────────────────────────────────────────────────────────┤
│ [待处理] [我发起] [历史归档]  ← 可保留为 Chips 或左列分段              │
├──────────────────┬──────────────────────────────────────────────┤
│ 汇报卡片列表       │  汇报阅读区：正文、附件、时间线、操作按钮            │
└──────────────────┴──────────────────────────────────────────────┘
```

### 7.3 步骤

#### D.1 Master-Detail

| 步骤 | 动作 |
| --- | --- |
| D.1.1 | 新建 `ReportMasterDetailLayout.vue`； refactor `ReportsView.vue` |
| D.1.2 | 左列卡片：标题、对方姓名、状态色点、时间；点击设 `selected=<reportId>` |
| D.1.3 | 右列：原卡片展开内容（正文、附件、路由时间线、动态操作按钮） |
| D.1.4 | query：`filter=pending|initiated|history` 替代 `tab=`；兼容旧 `tab` redirect |
| D.1.5 | 列表切换 filter 时保留 selected 若仍存在于当前列表，否则清空 |

#### D.2 撰写汇报 Drawer

| 步骤 | 动作 |
| --- | --- |
| D.2.1 | 删除原「发起汇报 → 选向上/向下 → 表单」两步 `ElMessageBox` 或分步 dialog |
| D.2.2 | 新建 `ReportComposeDrawer.vue`：字段 — **收件人**（下拉，选项文案：`上级 - 张三 (向上)` / `下级 - 研发组 (向下)`）、标题、正文、审批流（可选）、附件 |
| D.2.3 | 选中收件人 → 前端推断 `direction=up|down`，提交时带正确 API 字段 |
| D.2.4 | 收件人列表：合并现有向上/向下 target API 为统一列表 + `direction` 元数据 |
| D.2.5 | 无可用链路时 Drawer 内提示「暂无可发起链路」，按钮 disabled |

**testid**：`reports-compose-button`、`reports-compose-drawer`、`reports-compose-recipient`、`reports-detail-panel`、`reports-filter-pending`。

**验收**：

- 处理多条待办时列表与详情同屏，无反复全屏跳转。
- 撰写汇报一步完成；方向由收件人隐式决定。
- E2E 汇报相关步骤（若有）更新选择器。

### 7.4 Phase D 出口清单

- [x] Reports Master-Detail + Compose Drawer
- [x] 旧 `?tab=` 兼容
- [x] user-manual §7 操作步骤可同步

---

## 8. Phase E — 组织管理（人员 + 部门）

### 8.1 人员管理

#### 目标

- 列表保持；选中员工 → **宽 Drawer**（非右侧 5 Tab）。
- Drawer 顶：头像区、姓名、状态徽章、高频操作（重置密码、编辑）。
- 内容：**垂直单页** + 左侧锚点（账号 / 档案 / 岗位与汇报 / 生命周期 / 权限）。

#### 步骤

| 步骤 | 动作 |
| --- | --- |
| E.1.1 | 新建 `PeopleDetailDrawer.vue` + `PeopleAnchorNav.vue` |
| E.1.2 | 将 `PeopleManagementView.vue` 五个 Tab 内容改为 `<section id="account">` 等锚点块 |
| E.1.3 | 锚点点击 `scrollIntoView`；滚动时 `IntersectionObserver` 高亮当前锚点 |
| E.1.4 | Drawer 宽度建议 `min(960px, 85vw)` |
| E.1.5 | 列表行点击打开 Drawer；关闭后保留列表筛选状态 |

**testid**：`people-detail-drawer`、`people-anchor-account`、`people-reset-password`。

### 8.2 部门管理

#### 目标

- 左 1/3：`el-tree` 部门树；右 2/3：选中部门详情（主管、下属列表、编辑/停用）。
- 右上：[+ 新建根部门]、[+ 添加子部门]。
- **本阶段不做**树节点拖拽排序（标记为 E.2.x-backlog）。

#### 步骤

| 步骤 | 动作 |
| --- | --- |
| E.2.1 | 新建 `DepartmentTreePanel.vue`、`DepartmentDetailPanel.vue` |
| E.2.2 | API：复用现有 departments 列表，前端 `buildTree(parent_id)` |
| E.2.3 | 选中节点 → 右侧表单（名称、编码、上级、负责人、排序、状态） |
| E.2.4 | 「下属人员」：调用人员列表 API `department_id=` 过滤 |
| E.2.5 | 停用/编辑与原表格行为一致 |

**testid**：`departments-tree`、`departments-detail-panel`、`departments-create-root`。

### 8.3 Phase E 出口清单

- [x] 人员 Drawer + 锚点导航
- [x] 部门树 + 详情分栏
- [x] 管理员 E2E 路径仍可达

---

## 9. Phase F — 总览 Dashboard

### 9.1 范围

- 总览小组件化（不合并任务中心）。
- 顶栏「最近截止任务」倒计时（精确到秒）。
- 待办/汇报在总览内联处理 Drawer（可选跳转任务/汇报中心）。

### 9.2 小组件规格

#### F.1 消息收件箱预览

| 项 | 说明 |
| --- | --- |
| 数据 | 最近 5 条未读或全部消息按时间倒序 |
| 交互 | 点击条目 → 打开 NotificationDrawer 并选中 **或** 跳来源 |
| 组件 | `OverviewMessageWidget.vue` |
| testid | `overview-widget-messages` |

#### F.2 公告栏 / 白板切换

| 项 | 说明 |
| --- | --- |
| UI | 单卡片容器；顶栏 Toggle「公告 \| 白板」 |
| 操作 | 有权限时：添加、删除（归档）；与现 HomeView 看板/公告 API 一致 |
| 组件 | `OverviewAnnouncementBoard.vue` |
| testid | `overview-widget-announcement-board` |

#### F.3 待办任务 / 待审汇报列表

| 项 | 说明 |
| --- | --- |
| 数据 | inbox 任务 + pending 汇报各 Top N |
| 交互 | 行点击 → `OverviewTaskActionDrawer` / 汇报处理 Drawer（复用 C/D 详情组件的 embed 模式） |
| 组件 | `OverviewTodoWidget.vue` |
| testid | `overview-widget-todos` |

#### F.4 顶栏倒计时

| 步骤 | 动作 |
| --- | --- |
| F.4.1 | `DeadlineCountdown.vue`：拉取当前用户 inbox+tracking 中带 `due_at` 的任务，取最近未来截止 |
| F.4.2 | 显示：`距「任务标题」截止 HH:MM:SS`；无截止任务时隐藏 |
| F.4.3 | 点击跳转 `/task-center?filter=tracking&selected=<id>` |
| F.4.4 | `setInterval(1s)` 更新；组件卸载清理 |

### 9.3 HomeView 重构步骤

| 步骤 | 动作 |
| --- | --- |
| F.3.1 | `HomeView.vue` 改为 grid 布局（2 列 responsive） |
| F.3.2 | 移除或弱化原「大数字卡片跳 task-center Tab」；改为 widget 内列表 |
| F.3.3 | 保留 `?announcement=<id>` 深链高亮 |
| F.3.4 | 保留快捷入口（任务中心、知识库、人员管理）可收拢为次要链接 |

### 9.4 Phase F 出口清单

- [x] 三小组件 + 倒计时上线
- [x] 总览可完成轻量待办/汇报处理或明确跳转
- [x] user-manual §4 同步

---

## 10. 横切关注点

### 10.1 `data-testid` 命名约定

```
{page}-{region}-{action}
例：task-center-create-task, reports-compose-recipient
```

Shell 级：`header-*`、`notification-*`、`global-memo-*`。

### 10.2 E2E 更新清单（按阶段）

| 阶段 | 文件 | 变更要点 |
| --- | --- | --- |
| A | `e2e/login.spec.ts` | 三场景可选加 case；弱密码断言 |
| B | `docker-gui-verification.spec.ts` §B | 侧栏无消息；铃铛截图 |
| C | `task-center.spec.ts`, docker-gui C1 | `filter=`/`selected=`；去 tab 点击 |
| D | docker-gui 汇报段 | Master-Detail、撰写 Drawer |
| E | docker-gui 管理员段 | 人员 Drawer、部门树 |
| F | docker-gui 总览段 | widget testid |

文档同步：`infra/docker/E2E-GUI-VERIFICATION.md`、`handbooks/e2e-gui-verification-automation-runbook.md`。

### 10.3 后端 API 增量汇总

| 端点 | 阶段 | 说明 |
| --- | --- | --- |
| `POST /auth/change-password` | A | 自助改密（若缺失） |
| `GET /auth/bootstrap-status` | A | 可选：显式空库检测，替代前端试探 |
| 汇报 compose targets 合并 | D | 可选：`GET /reports/compose-targets` 返回 `{ id, label, direction }[]` |

其余阶段 **复用** 现有 task-center、messages、reports、people、departments API。

### 10.4 性能与 UX

- NotificationDrawer：首屏只拉 20 条；滚动加载。
- 总览 widget：并行请求，单 widget 失败不阻塞整页。
- Master-Detail：右列详情 lazy load（选中后再拉完整详情）。
- 移动端：Drawer 全宽；任务中心 Master-Detail 小屏改为列表 → 详情全屏栈（`isMobileViewport` 已有）。

### 10.5 风险

| 风险 | 缓解 |
| --- | --- |
| E2E 大量 selector 失效 | 分阶段合并；保留 legacy redirect 一个版本 |
| 任务中心 refactor 范围大 | C 先拆 composable，再改布局；TasksView 逻辑少动 |
| 改密 API 缺失阻塞 A | A.3 可先 UI + mock，后端并行 |
| 汇报收件人合并列表 UX 复杂 | D.2 选项分组：`上级` / `下级` optgroup |

---

## 11. 文档与进度同步

每阶段 **Done** 后：

1. 更新 [`progress.md`](../progress.md) IA-1…IA-n 行状态。
2. 更新 [`handbooks/user-manual.md`](../handbooks/user-manual.md) 对应章节路径与截图说明（Step 4）。
3. 必要时更新 [`architecture.md`](../architecture.md) 前端模块小节（仅结构变化时）。

---

## 12. 验收总表

| 阶段 | 核心验收标准 |
| --- | --- |
| **A** | 弱密码有明确中文提示；登录三场景；设置可改密 |
| **B** | 消息仅铃铛+Drawer；`/messages` 仍可达；侧栏项正确 |
| **C** | 任务中心无 4 Tab；Chips+Master-Detail；模板/备忘迁出 |
| **D** | 汇报 Master-Detail；撰写 Drawer 单步、收件人定方向 |
| **E** | 人员宽抽屉+锚点；部门树+详情 |
| **F** | 总览三 widget；顶栏倒计时；不合并任务中心 |

**全里程碑完成**：`npm run test:e2e:docker-gui` 通过；user-manual 与 router 一致；IA plan §3 标记为「已由 ui-refactor-spec-v2 取代」。

---

*文档版本：v2.0 · 2026-05-19 · 对应 user-manual 审阅批注冻结版*
