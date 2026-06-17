# 领域：知识库与 AI (Knowledge & AI)

> 🌡️ WARM — 涉及文档库、RAG、`@系统`、Tool Calling 时读取。

**关联 schema**: `data-contracts.md` §10.32–10.33

---

## 知识库

- Markdown 文档：`documents` + `document_embeddings`（`pgvector`）
- 切块、嵌入、检索在后端服务层
- 前端：知识库工作台路由（见 `frontend/src/views/`）

---

## AI Router

| 入口 | 行为 |
|------|------|
| `@系统` / `/` | 前端拦截 → `LLMRouterService` |
| Tool Calling | LLM 选工具 → 后端执行 → 组织回复 |

**原则**: LLM 是意图路由器；业务数据来自 service/DB，非模型编造。

---

## 关键代码

| 路径 | 作用 |
|------|------|
| `backend/app/services/llm_router_service.py` | 路由与回复编排 |
| `backend/app/services/knowledge_retrieval_service.py` | RAG 检索 |
| `backend/app/services/tool_registry_service.py` | 工具注册 |
| Tool schemas | Pydantic v2，复用 API schema |

---

## 约束

- **禁止** LangChain
- 使用官方 `openai` Python SDK
- 工具执行须权限与数据范围校验

---

## 后续增强

- 工具面扩展与安全观测
- 文档治理与检索质量运营

见 `project-brief.md`、`roadmap.md`。
