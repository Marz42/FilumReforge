---
type: paradigma-plan
title: "2026-08-10 Iteration 4 UAT 验收准备计划"
description: "为 Iteration 4、设计器 Phase 2 与 S-01 人工验收提供只读前置检查，不替代业务验收。"
tags: [plan, iteration-4, uat, preflight, task-stats]
timestamp: 2026-08-10T16:30:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 4 验收准备, UAT 前置检查, S-01 验收]
    en: [iteration 4 UAT preflight, UAT prerequisites, S-01 acceptance]
  relations:
    depends_on:
      - 2026-08-10-template-governance-audit-plan.md
      - ../manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md
---

# Iteration 4 UAT 验收准备计划

## 目标

把“能否开始验收”从口头盘点变为产品内的只读检查，同时严格区分两个结论：

- **验收准备完成**：目标环境具备必要账号、模板和统计样本。
- **人工验收通过**：员工按清单实际操作并记录结果；只能由人工给出。

## 范围

入口位于“任务模板 → 验收准备”，复用现有模板管理权限。检查项为：

| ID | 检查 | 阻断规则 |
|----|------|----------|
| P-01 | 模板范围/父子依赖数据治理 | 确定错误阻断；warning/review 提醒人工确认 |
| P-02 | 候选部门具备负责人和至少 3 名活跃成员 | 无候选部门时阻断 |
| P-03 | 可直接发起、不依赖 legacy `run_kind` 的通用 ACTIVE 模板 | 缺失时警告，可在 D-01 中创建 |
| P-04 | 视频批次与制作子模板均有 ACTIVE 修订版本 | 缺失时阻断兼容黄金路径 |
| P-05 | 有可管理设计器草稿 | 缺失时警告 |
| P-06 | 当前月新增、完成、到期、未完成统计样本 | 缺项时警告，避免只测空状态 |
| P-07 | 人工业务验收 | 永远标为人工，不自动转为通过 |

## 设计边界

- 服务只读，不创建账号、任务、部门或模板，不自动修改治理问题。
- 视频模板只在验收辅助层通过稳定 `base_code` 找到参考包的新旧修订版本；Runtime 继续把视频视为普通模板工作流。
- 沿用现有模板管理权限和 404 隐藏策略；KI-011 系统管理员业务边界不在本批改变。
- `preflight_ready=true` 只表示没有阻断项，响应始终保留 `manual_uat_required=true`。

## 验证

- 后端服务测试覆盖缺少前置条件、完整候选环境、新版视频模板识别与越权隐藏。
- API 测试确认可管理者可查询、普通员工得到 404，且接口不会声称人工验收完成。
- 前端测试覆盖结果展示、人工验收提示和候选模板跳转。
- 全量后端/前端回归、类型检查、构建、lint、compileall 与 Paradigma 检查作为提交门禁。

## 出口

代码与文档完成后，下一步由目标环境人员依次执行“数据检查”→“验收准备”→人工 UAT checklist。只有清单必测项通过并签字，才可把 Iteration 4 / 设计器 Phase 2 / S-01 标记为 UAT 通过。
