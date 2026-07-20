---
type: paradigma-known-issue
title: "KI-010: 活动时间线需重做为更有指向性的留痕"
description: "当前任务活动时间线事件粒度与文案不够指向性，暂以默认折叠降低干扰；后续应重做为更准确、可操作的协作留痕。"
tags: ["known-issue", "activity-timeline", "task-detail", "UX", "E2E"]
timestamp: "2026-07-20T15:10:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["活动时间线", "折叠", "留痕", "指向性", "任务详情"]
    en: ["activity timeline", "collapse", "audit trail", "task detail"]
---

# KI-010: 活动时间线需重做为更有指向性的留痕

> **临时处置**：任务详情中的「活动时间线」默认折叠（可展开查看），避免干扰主操作区。  
> **正式修复**：后续单独重做时间线信息架构与事件文案，不在本轮 C 闭环修修补补。

## 现象

- 活动时间线默认展开时占用大量详情纵向空间。
- 现有评论/日志混排事件对业务协作的指向性不足（谁该看、发生了什么、下一步是什么不够清楚）。
- 部分操作成功后若活动接口异常，曾被前端当成整次操作失败（已另做软失败兜底；根因见活动序列化的 ORM 加载问题）。

## 期望（后续重做方向）

1. **事件语义**：按业务动作分类（指派/转办/开工/提交/验收/打回等），文案可读且指向责任人。
2. **信息密度**：默认展示关键里程碑；细节按需展开，避免全量流水账。
3. **一致性**：操作人、处理人标签统一走服务端 `*_label`，不依赖前端用户目录可见性。
4. **可靠性**：活动接口失败不得掩盖主操作成功态。

## 当前临时方案

- 前端 `TaskDetailShell`：`el-collapse` + `activityTimelineExpanded` 默认空数组 → 默认折叠。
- 记档本 KI，待产品/UX 排期后重做。
