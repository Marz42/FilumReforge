# 领域：组织与人事 (HR & Org)

> 🌡️ WARM — 涉及档案、部门、权限、生命周期时读取。

**关联 schema**: `data-contracts.md` §10.3–10.11 · **计划**: `plans/improvements-stage2-implementation-plan.md`

---

## 职责边界

| 子域 | 能力 | 状态 |
|------|------|------|
| IAM | JWT、邀请注册、角色 admin/hr/employee | 已实现 |
| Organization | 部门树、负责人、capabilities JSONB | 已实现 |
| Profiles | 一人一档、`custom_fields` | 已实现 |
| Positions | 岗位目录、多任职、直属/虚线汇报 | 已实现 |
| Field Policy | 字段定义 + 字段级权限 | 已实现 |
| Lifecycle | 入转升奖惩离返聘 | 已实现 |
| Delegation | 代理授权、时间窗生效 | 已实现 |

---

## 核心流程

1. **字段权限**: `profile_field_definitions` → `profile_field_permissions` → `ProfileFieldPolicyService` 裁剪视图
2. **生命周期**: `HRLifecycleService` 写 `employment_events` → 可选异步入队 `process_employment_event_job` → 模板/审批实例化回写
3. **人员工作台**: `/people` — `PeopleManagementService` 聚合账号/档案/岗位/生命周期/权限

详见 `architecture.md` §6.5、§6.6。

---

## 关键代码

| 路径 | 作用 |
|------|------|
| `backend/app/models/hr_governance.py` | HR 治理模型 |
| `backend/app/services/profile_service.py` | 档案读写 |
| `backend/app/services/hr_lifecycle_service.py` | 生命周期 |
| `backend/app/services/access_control.py` | 组织范围与代理解析 |
| `backend/app/services/people_management_service.py` | 人员聚合 API |
| `frontend/src/views/PeopleManagementView.vue` | 人员工作台 |

---

## 已知缺口

- 生命周期**规则化默认映射**与前端结构化配置入口
- 字段权限可视化规则管理增强
- 公开/审批式注册（邀请制已落地）

---

## 约束

- 离职：停用账号，**不物理删除**已建档员工
- 高敏字段必须在 `custom_fields` + 字段策略下访问
- Leader 由组织关系推导，非独立全局角色
