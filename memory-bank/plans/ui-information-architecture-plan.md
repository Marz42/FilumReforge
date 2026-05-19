# UI 信息架构重构规划（里程碑草案）

本文件为**独立里程碑**规划，与附件白名单 / E2E 扩面解耦；实施前需单独排期与验收。

## 1. 目标

- 降低「同一能力多入口、多命名」带来的认知成本。
- 让**任务**、**汇报**、**人员**、**消息**四条主线的动线在壳层导航与页面内 Tab 上更可预测。
- 为 Playwright 保留或补充稳定 `data-testid`，避免纯文案定位。

## 2. 现状痛点（归纳）

- **任务**：任务中心四标签 + 页头建立任务 Drawer + 跟踪深链 `?selected=`，新用户易混淆「待办 / 跟踪 / 历史」与详情面板关系。
- **汇报**：「发起汇报」弹窗内再选向上/向下，与侧栏「汇报中心」双概念；历史 / 我发起 / 待处理与列表卡片信息密度高。
- **人员工作台**：多 Tab（账号 / 档案 / 岗位 / 生命周期 / 权限）与组织管理入口分散。
- **消息**：筛选维度多，与任务/汇报回跳路径依赖通知 payload，部分场景需两次跳转。

## 3. 分期建议

> **v2 细化**：逐步实施步骤、组件拆分、URL 迁移与 E2E 清单见 **[`ui-refactor-spec-v2.md`](./ui-refactor-spec-v2.md)**（Phase A–F）。下表保留里程碑编号与 v2 阶段映射。

| 阶段 | 范围 | 产出 | v2 映射 |
| --- | --- | --- | --- |
| IA-0 | 走查 + 用户动线文档 | **已完成**：[`handbooks/user-manual.md`](../handbooks/user-manual.md) v1 + 审阅批注 | — |
| IA-1 | 登录、设置、壳层、消息降级 | 三场景登录、设置三分栏、铃铛 Drawer、侧栏去消息 | Phase A + B |
| IA-2 | 任务中心 | Quick Chips + Master-Detail；模板/备忘迁出 | Phase C |
| IA-3 | 汇报中心 | Master-Detail + 「撰写汇报」抽屉 | Phase D |
| IA-4 | 人员、部门、总览 | 人员宽抽屉；部门树；Dashboard 小组件 | Phase E + F **done** |

## 4. 与测试的协调

- 任何导航或 `data-testid` 变更需同步更新：`frontend/e2e/docker-gui-verification/`、`frontend/e2e/task-center.spec.ts`、`infra/docker/E2E-GUI-VERIFICATION.md`。
- 优先在 **IA-0** 冻结一版「锚点清单」，再动 UI。

## 5. 非目标（本里程碑）

- 不改变后端领域模型与 API 契约（除非配合 UX 必须增加字段）。
- 不与图引擎 / 工作流 E 运行时合并同一次发布。
