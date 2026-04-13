# Copilot Instructions — Project Filum (FilumReforge)

## Project Overview

**Project Filum** is a lightweight, AI-enhanced internal enterprise management platform for 50–100 person companies. It unifies HR records, task workflows, and messaging in a single system with deep LLM integration. The repository is currently in the **planning/pre-implementation phase** — `memory-bank/` holds the authoritative design documents.

---

## Architecture

**Modular Monolith** — explicitly chosen over microservices to minimize operational overhead at this scale. Keep all business logic in a single deployable unit with well-separated internal modules.

### Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 (Composition API) + TypeScript + Vite + Element Plus + Pinia + Vue Router |
| Backend | Python 3.10+ + FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + Alembic |
| AI/LLM | Official `openai` Python SDK — **no LangChain** |
| Database | PostgreSQL 15+ (JSONB for dynamic fields, pgvector reserved for RAG) |
| Cache/Queue | Redis (session, org-tree cache, task broker) |
| Async Workers | Celery or ARQ (email, reports, LLM calls) |
| Deployment | Docker Compose + Nginx |

---

## Key Design Conventions

### Notification System
All notifications go through a **single adapter bus**. Business logic calls `NotificationService.send(message_obj)` and never talks to email/WebSocket/WeCom directly. The gateway dispatcher routes to the appropriate adapter (Email, WebPush, future WeCom).

### LLM Integration
The LLM is an **intent routing engine**, not a chatbot. When the user types `@系统 ...` or `/...`, the frontend intercepts and sends to a backend LLM Router. The router uses **OpenAI Function Calling** to invoke registered backend tools (e.g., `get_department_tasks(...)`), feeds the raw JSON result back to the LLM, and returns a natural-language reply. Use **Pydantic v2 models as the JSON Schema** for tool definitions — do not use LangChain or any wrapper framework.

### HR Profile Fields
Use PostgreSQL **JSONB** for dynamic/custom employee fields (skills, emergency contacts, etc.). Core identity fields go in typed columns; anything domain-specific or variable goes in `custom_fields (JSONB)` on the `profiles` table.

### Task State Machine
Tasks follow a strict state machine: `Todo → Doing → Review → Done`. Enforce transitions server-side; do not allow arbitrary status jumps.

### RBAC & Data Isolation
Two levels of access control:
- **Role-level**: Admin / HR / Employee — controls UI feature visibility
- **Data-level**: Org-tree scoping — e.g., a department manager can only query their subtree

### Frontend Patterns
- Use **Composition API** with `<script setup>` syntax
- State management via **Pinia** stores (not Vuex)
- All HTTP calls via **Axios**
- Target B2B ("后台管理") UX with Element Plus components

### Backend Patterns
- FastAPI route handlers are thin; business logic lives in service classes
- All DB operations use **async SQLAlchemy 2.0** sessions
- Schema migrations managed exclusively via **Alembic**
- Request/response models are Pydantic v2 schemas — leverage them for LLM tool definitions too

### Task-Bound Communication (工作留痕)
Never build a standalone chat feature. All work-related communications, comments, and attachments MUST be tightly coupled to a specific `Task` via the `task_comments` table. This ensures absolute traceability and contextual cohesion.

### RAG Knowledge Engine (AI知识库)
For company policies and SOPs, use PostgreSQL with `pgvector`. Documents are stored in markdown, chunked, embedded via an Embedding model, and stored in `document_embeddings`. The LLM Router will perform similarity searches (RAG) before answering policy-related questions.

### Utility Tool Registry (扩展工具池)
Design the system to allow plug-and-play internal tools (e.g., invoice generator, format converter). Tools should be isolated Vue components on the frontend and dedicated FastAPI routers on the backend. Expose these tools to the LLM via Function Calling.


---



## Domain Models (intended)

**Base & HR:**
- `users` — auth base (`id`, `email`, `password_hash`, `role`, `status`)
- `profiles` — HR detail (`user_id`, `real_name`, `department_id`, `custom_fields JSONB`)
- `departments` — org tree (`id`, `name`, `parent_id`, `manager_id`)

**Workflow & Collaboration:**
- `tasks` — core workflow (`id`, `title`, `creator_id`, `assignee_id`, `status`, `due_date`)
- `task_logs` — audit trail (`task_id`, `action_type`, `timestamp`)
- `task_comments` — **CRITICAL for communication** (`id`, `task_id`, `user_id`, `content`, `attachments`, `created_at`)

**Knowledge Base (RAG):**
- `documents` — SOPs and policies (`id`, `title`, `content_md`, `author_id`, `category`)
- `document_embeddings` — pgvector storage (`id`, `document_id`, `chunk_text`, `embedding VECTOR`)

---

## Development Phases

The project is built in four sequential phases. When implementing features, check which phase they belong to:

1. **Phase 1 – Foundation**: Framework setup (Vue3 + FastAPI + PG), users, department tree, HR profiles CRUD, task creation/assignment, and base notification bus.
2. **Phase 2 – Collaboration & Stats**: Task state machine, `task_comments` (in-task communication), background timeout reminders (Celery/Email), and BI Analytics (task completion/workload dashboards).
3. **Phase 3 – Knowledge & AI Brain**: Markdown knowledge base CRUD, Embedding integration + pgvector, RAG similarity search, allowing employees to ask AI about internal policies.
4. **Phase 4 – Platform & Tools Registry**: Deepen the `@系统` LLM Intent Router (Function Calling), build the plugin/utility tool registry standard, UI polish, and PWA integration.

When writing new code, anchor it to its phase so scope stays clear.

## IMPORTANT INSTRUCTIONS:

- Always read memory-bank/@architecture.md before writing any code. Include entire database schema.
- Always read memory-bank/@design-document.md before writing any code.
- After adding a major feature or completing a milestone, update memory-bank/@architecture.md.
- Use Simplified Chinese to communicate with the developer.
- After adding a major feature or completing a milestone, commit your changes using git.

