---
mode: agent
description: 审查 memory-bank 与实际代码是否对齐，并输出结构化评估报告
---

# 审查 memory-bank 与实现对齐

你的任务是检查 `memory-bank/` 文档、README 体系和当前实际代码实现之间是否一致，并在需要时输出一份详细评估报告到 `memory-bank/`。

## 目标

- 确认当前实现和文档是否对齐
- 找出架构说明、阶段状态、运行命令、模块边界、数据库事实中的漂移点
- 区分“文档过时”和“实现缺失”，不要混为一谈
- 输出一份可执行的评估报告，报告中必须给出证据路径和建议动作

## 必读资料

先阅读以下文件：

- `memory-bank/architecture.md`
- `memory-bank/design-document.md`
- `memory-bank/progress.md`
- `memory-bank/implementation-plan.md`
- `README.md`
- `backend/README.md`
- `frontend/README.md`

## 事实核对范围

至少核对以下代码侧事实来源：

- `backend/alembic/versions/` 中的迁移
- `backend/app/models/` 中的模型
- `backend/app/services/` 中的核心服务
- `backend/app/api/routes/` 中的接口入口
- `backend/app/main.py` 与 `backend/pyproject.toml`
- `frontend/src/router/`、`frontend/src/views/`、`frontend/package.json`
- `backend/tests/` 与 `frontend/tests/` 中能够证明当前行为的测试

## 审查要求

1. 先给出“当前对齐度概览”
2. 再按主题分组列出问题：
   - 项目阶段与交付状态
   - 架构与模块边界
   - 数据库 / 模型 / 迁移
   - API 与前端入口
   - 运行 / 测试 / 开发命令
   - 已知缺口与后续计划
3. 每个问题都要标注：
   - 严重度：高 / 中 / 低
   - 类型：文档漂移 / 实现缺失 / 表述含混
   - 证据：具体文件路径
   - 建议：更新文档、补实现、补测试，或保留为后续范围
4. 明确哪些内容已经对齐，避免报告只写问题不写事实

## 输出要求

- 除非用户另有指定，把报告写到 `memory-bank/alignment-assessment-YYYYMMDD.md`
- 报告语言使用简体中文
- 报告结构建议如下：

```md
# Project Filum 文档与实现对齐评估

## 1. 结论摘要
## 2. 对齐项
## 3. 问题清单
## 4. 建议修复顺序
## 5. 证据索引
```

## 重要限制

- 这项审查默认不修改业务代码，除非用户明确要求顺手修复
- 不要把 `design-document.md` 中的目标态当作当前实现事实
- 如果 `memory-bank` 与代码冲突，必须以可验证的代码、迁移、测试和运行命令为准