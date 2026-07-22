# Spec: Template Engine Decouple — Tags, Graph-Derived Behavior, Designer Gaps

**Date:** 2026-07-22  
**Status:** Design (Phase 0) — no implementation in this document  
**Input:** `docs/superpowers/reports/2026-07-21-template-designer-audit.md`  
**Domain intent:** `memory-bank/knowledge/domains/task-center.md` §7  
**Data model:** `memory-bank/knowledge/contracts/database/graph-engine-schema.md`  
**Active task:** `memory-bank/runtime/active-task.md`

---

## 1. Design Philosophy

### 1.1 Why decouple

The workflow template engine is a **generic DAG runtime** (`templates → nodes → edges → instances`). Video选题会 (batch / production) is one **product profile** built on that engine — not the engine’s type system.

Today, authoring treats `config.run_kind ∈ {batch, production}` as a template-level product type that gates:

- direct instantiation
- schedule eligibility
- list/designer labels (“批次 / 制作”)

That couples the blank canvas to one vertical, conflicts with node-level truth (`config.kind`, `config.ui_profile`, fork/`child_template_code`), and blocks “one template, multiple graph shapes.”

### 1.2 What changes

| Axis | From (system type) | To (engine-native) |
|------|--------------------|--------------------|
| Classification | `config.run_kind` as authoring type | **User tags** — pure labels, **zero behavioral impact** |
| Runtime gates | Branch on `run_kind` | **Derive capabilities from graph + explicit opt-in flags** |
| Node UI binding | Buried in raw JSON | Keep `ui_profile` as **internal runtime mechanism**; do **not** expose as a product “模板类型” |
| Legacy video v1 | Written on every save | **Read-only** on existing seeds; **new templates never write `run_kind`** |

### 1.3 Non-goals (this redesign)

- Replacing video v1 runtime panels / fork APIs in one shot
- Removing `ui_profile` from nodes or Task metadata
- Making ARCHIVED templates editable or re-activatable (M-09 optional later)
- Turning tags into a permission or routing system

### 1.4 Guiding rule

> If a behavior cannot be justified by **graph structure**, **explicit opt-in config** (`schedulable`, `launch_schema`, fork refs), or **instance context**, it does not belong in a template-level enum.

---

## 2. Template Type Refactor

### 2.1 Current state

**Storage**

- `workflow_graph_templates.config.run_kind` ∈ `{batch, production}` (JSONB key, not a DB column)
- API summary/detail **projects** `run_kind` to a top-level read field
- Seeds: `topic_meeting_batch_v1` → `batch`; `video_production_per_topic_v1` → `production`

**Consumers (behavioral)**

| Consumer | Rule today |
|----------|------------|
| Frontend `templateSupportsDirectInstantiation` | `run_kind === 'production'` → disable |
| `template_is_schedulable` | requires `run_kind == batch` (defaulting missing to batch) + `schedulable` + multi_instance + not streaming |
| Designer radio / list “类型” | Writes & displays batch/production as product type |
| Fork / instance context | Instance `context.run_kind` copied from template for ROOT / production panels |

**Structural truth already in the graph (underused for gates)**

- Nodes: `config.kind == multi_instance` + `expand_from`
- Fork target: parent `config.child_template_code` or N2 `aggregate_schema.on_confirm.child_template_code`
- Launch form: `config.launch_schema`
- Schedule opt-in: `config.schedulable == true`
- Node UI: `config.ui_profile` (e.g. `video_n1_capture`, `video_production_step`) — **runtime**, not template taxonomy

### 2.2 Target state

#### 2.2.1 User tags (classification only)

- Templates carry `tags: string[]` (normalized, case-sensitive display; uniqueness per template after trim).
- Tags are **user vocabulary** (e.g. `视频`, `选题会`, `制作链`, `周会`). Engine never switches on tag values.
- Tags may appear in list chips, search, and filters.
- Suggested defaults for seeded video templates (non-binding): `["视频", "选题会"]` / `["视频", "制作"]` — applied by seed/migration helper, not by runtime logic.

**Storage recommendation**

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| A. `config.tags` | No Alembic | Stuck inside immutable ACTIVE `config`; conflates with behavioral keys | Reject for ACTIVE tag edits |
| B. Column `tags JSONB NOT NULL DEFAULT '[]'` | Searchable; metadata-editable without forking definition | Requires migration | **Adopt** |
| C. Junction table | Normalized tag catalog | Overkill for free-form labels | Defer |

Add index-friendly GIN on `tags` if filter-by-tag becomes hot; Phase 1 may use `tags ?| array[...]` without GIN.

**Mutability**

| Field | DRAFT | ACTIVE | ARCHIVED |
|-------|-------|--------|----------|
| Graph / `config` / `context_schema` / scope | editable | **immutable** (fork new version) | immutable |
| `name` / `description` | editable | **immutable** (fork) | immutable |
| **`tags`** | editable | **editable** (metadata-only) | read-only |

This intentionally separates **classification** from **definition immutability** (fixes a slice of M-04 without weakening the publish contract).

#### 2.2.2 Behavior derivation (capabilities)

Capabilities are computed server-side and returned on list/detail/designer reads so UI and schedulers share one truth.

```text
TemplateCapabilities {
  can_instantiate_directly: bool
  can_schedule: bool
  is_fork_target: bool          # referenced by ≥1 other template fork config
  has_multi_instance: bool
  has_launch_entry: bool        # ≥1 topological start node
  derived_hints: string[]       # optional UX strings, not enums
}
```

**Definitions (generic DAG)**

1. **`has_launch_entry`**  
   Template has ≥1 node with **indegree 0** on non-reject edges (topological start set). Empty graphs → false.

2. **`can_instantiate_directly`**  
   - `status == active`  
   - AND `has_launch_entry`  
   - AND **not** `is_fork_only`  
   where  
   `is_fork_only = is_fork_target AND NOT has_direct_launch_surface`  
   `has_direct_launch_surface = launch_schema present (non-empty object/array) OR config.schedulable == true OR has_multi_instance`  

   Rationale: fork-child graphs (e.g. production chain) usually still have topological starts, but lack a **direct launch surface**. Parent/collector graphs expose `launch_schema` and/or multi_instance fan-out. This avoids a new template-level enum while matching video v1 intent.

3. **`can_schedule`**  
   - `config.schedulable === true` (explicit opt-in — “schedule config”)  
   - AND `has_multi_instance` (`kind == multi_instance` with non-empty `expand_from`)  
   - AND `can_instantiate_directly`  
   - AND `aggregate_mode != "streaming"` (unchanged operational constraint)  
   - **No** `run_kind` check.

4. **`is_fork_target`**  
   True if any **other** template (any status, or restrict to `active|draft` for UX) references this template via:
   - `config.child_template_code` equals this `code` or `base_code` (match policy: prefer exact `code`, fallback `base_code` of latest active), or
   - any node `config.aggregate_schema.on_confirm.child_template_code` (same match).

**`derived_hints` (UI only, localized later)**

Examples — never used as gates:

- `可直接发起` if `can_instantiate_directly`
- `可调度` if `can_schedule`
- `可作为子流程目标` if `is_fork_target`
- `仅子流程` if `is_fork_only`

#### 2.2.3 `ui_profile` policy

- Remains on **node** `config.ui_profile` and is copied to Task metadata at instantiation.
- Phase 2 adds structured authoring (dropdown of known profiles + custom string) — still framed as **节点运行时外观 / Action Profile**, not “模板类型”.
- Product UI must not introduce a template-level “UI 配置文件” concept that replaces tags or capabilities.

#### 2.2.4 Instance `context.run_kind` (runtime label)

- Instance context may still carry `run_kind` for **video v1 panel selection** during transition.
- Write path:
  - **Legacy templates** with `config.run_kind` → copy into instance context (unchanged).
  - **New templates** without `config.run_kind` → derive a **compat label** only when needed by existing panels:
    - if `is_fork_only` or activated via fork child path → `"production"`
    - else if `has_multi_instance` → `"batch"`
    - else omit / `"graph"`
  - Long-term: panels should key off `ui_profile` / graph shape; `run_kind` on instances becomes optional legacy.

### 2.3 Migration plan for legacy templates

#### 2.3.1 Data

| Artifact | Action |
|----------|--------|
| Existing `config.run_kind` on `topic_meeting_batch_v1` / `video_production_per_topic_v1` (and forks) | **Keep as read-only legacy**. Do not strip in Phase 1. |
| New blank templates / new saves | **Do not write** `run_kind`. Designer removes the control that sets it. |
| Clone / “另存新版本” from legacy | Preserve source `run_kind` in forked `config` for continuity until consumers fully migrated; document as legacy carry-forward. |
| `tags` column | Backfill `[]`; optionally seed tags for the two video codes via data migration or seed script. |

#### 2.3.2 Dual-read window

| Layer | Old consumer | New consumer |
|-------|--------------|--------------|
| Direct instantiate | If `config.run_kind == production` → deny (compat) | Prefer `capabilities.can_instantiate_directly`; if capabilities computed, **capabilities win**; if computation unavailable, fall back to legacy `run_kind` |
| Schedule | `run_kind == batch` | `can_schedule` derivation (no run_kind) |
| List “类型” | batch/production tags | capabilities hints + user tags |
| API field `run_kind` | Keep projecting from config when present | Also return `tags` + `capabilities`; mark `run_kind` **deprecated** in OpenAPI description |

**Compat function (conceptual)**

```text
supports_direct_instantiation(template):
  if capabilities computed:
    return capabilities.can_instantiate_directly
  # legacy fallback only
  if config.run_kind == "production":
    return false
  return template.status == active and has_launch_entry
```

#### 2.3.3 Deprecation exit criteria

Remove dual-read / stop projecting `run_kind` when:

1. Instantiation, schedule, and fork services no longer read template `config.run_kind` for gates.
2. Frontend no longer calls `templateSupportsDirectInstantiation` based on `run_kind`.
3. Seed still may keep the field for archaeology, or a later cleanup migration deletes it from JSON.

---

## 3. UI Changes

### 3.1 Template list (`GraphTemplatesPanel` / `TaskTemplatesView`)

| Change | Detail |
|--------|--------|
| **Archive action (M-01)** | Per-row action for `active` (and optionally `draft` → prefer delete for draft). Confirm dialog: “归档后不可原地编辑；可在列表中筛选查看。” Success toast + refresh. |
| **Archived visibility (M-02)** | Status filter: `全部 / 草稿 / 已发布 / 已归档` (default: 草稿+已发布, i.e. current behavior). When “全部” or “已归档”, archived rows appear. |
| **Search (M-05)** | Text box: substring match on `name` and `code` (client-side OK if list payload remains modest; else server `q=`). |
| **Replace “类型” column (M-03)** | Remove 批次/制作/图 product tags. Show: (1) user **tags** chips; (2) compact capability hints (`可发起` / `仅子流程` / `可调度`) from `capabilities`. |
| **Instantiate button** | Enable iff `capabilities.can_instantiate_directly` (compat dual-read during migration). |
| **Archive vs delete copy** | Delete remains draft-only. Fix misleading copy that conflates Run archive with template `status=archived`. |

### 3.2 Designer (`GraphTemplateDesignerView`)

| Change | Detail |
|--------|--------|
| **Remove template-type radio (M-03)** | Delete “模板类型：批次 / 制作” control and any save path that writes `run_kind`. |
| **Tag editor** | Multi-select / tag-input; save via tags API (or included in draft save + dedicated ACTIVE patch). |
| **Capability readout** | Read-only panel: “可直接发起 / 可调度 / 子流程目标” computed from server, refresh after graph save/validate. |
| **Archive button (M-01)** | Toolbar for non-draft (at least `active`): Archive → confirm → navigate back to list with status=archived filter optional. |
| **Active edit contract (M-04)** | If `status != draft`: disable “保存设置”, graph edits, rename-in-place. Primary CTA: **另存新版本 / 派生草稿** then edit. Show banner: “已发布模板不可原地修改。” |
| **Legacy `run_kind` display** | If `config.run_kind` present, show muted read-only badge “遗留字段 run_kind=…” in advanced section — not editable. |
| **`ui_profile` (Phase 2 / M-06)** | On selected node: dropdown of known profiles + optional custom; still under node inspector, labeled as runtime profile — not template type. |
| **`context_schema` (Phase 2 / M-07)** | New designer section / tab: structured key editor with fallback JSON. |
| **launch_schema / routing (Phase 2 / M-08)** | Continue F-26: form builders; JSON textarea as escape hatch only. |

### 3.3 Rename dialog (`GraphTemplateEditDialog`)

- Remove editable rename for ACTIVE/ARCHIVED; show status + “派生新版本后可改名”.
- Remove `run_kind` as type label; show tags + capability hints.
- Optional: allow **tags-only** edit on ACTIVE from this dialog.

### 3.4 Instantiate dialog

- Drop batch/production badge; show tags.
- Gate open/submit on `can_instantiate_directly`.

### 3.5 Archive UX details

| Surface | Placement | Confirm |
|---------|-----------|---------|
| List row | Actions dropdown / button next to 设计 | “确认归档「{name}」？” |
| Designer | Toolbar near 发布 | Same; on success leave designer |

**Out of scope for Phase 1:** unarchive (M-09). Document as future: `archived → active` must re-run sibling unique-ACTIVE archive rules.

---

## 4. Backend Changes

### 4.1 API

| Endpoint / field | Change |
|------------------|--------|
| `PATCH .../templates/{id}/status` `{status:"archived"}` | **Already exists.** Tighten optional: only `active → archived` (draft keeps DELETE). Warn/block if ACTIVE schedules exist (409 with clear message) — recommended P1. |
| Frontend `archiveGraphTemplate(id)` | New client wrapper → existing status PATCH (M-01). |
| `GET` manage list | Query: `status` (multi), `q` (name/code ilike), optional `tag`. **Include ARCHIVED** when requested (M-02/M-05). Default status filter remains draft+active for backward compatible callers. |
| Summary/Detail/Designer schemas | Add `tags: string[]`, `capabilities: TemplateCapabilities`. Keep `run_kind` projected when present; document deprecated. |
| `PATCH .../templates/{id}/tags` | New metadata endpoint: body `{ tags: string[] }`; allowed for DRAFT and ACTIVE; reject ARCHIVED. |
| Draft `PATCH .../templates/{id}` | Stop accepting / silently ignore writes to `config.run_kind` from new clients; if client sends it on blank templates, strip unless template already had legacy key (preserve-only). |
| Instantiation `POST .../runs` | Gate with capabilities (+ legacy fallback). |
| Schedule create/validate | Use `template_is_schedulable` without `run_kind`. |

No dedicated `/archive` route required.

### 4.2 DB

| Change | Notes |
|--------|-------|
| Alembic: `tags JSONB NOT NULL DEFAULT '[]'` on `workflow_graph_templates` | Backward compatible; no drop of `config.run_kind` |
| Optional GIN index on `tags` | Phase 1.5 if tag filter used |
| No new status enum values | `archived` already exists |
| No `archived_at` required | Use `updated_at` + status; optional later |

Update `graph-engine-schema.md` / data-contracts when implemented (not in this design-only commit).

### 4.3 Service layer

| Service | Change |
|---------|--------|
| `WorkflowGraphTemplateAdminService` | `list_manageable_templates(status_filter, q, tag)`; compute `capabilities`; tags update; optional archive transition guard; strip `run_kind` on blank create |
| Shared `template_capabilities(template, nodes, edges, fork_index)` | Pure function used by admin, schedule, instantiation |
| `template_is_schedulable` | Remove `run_kind == batch`; align with §2.2.2 |
| `WorkflowVideoInstantiationService` | Direct instantiate gate via capabilities; instance `run_kind` write per §2.2.4 |
| `WorkflowVideoForkService` | Keep resolving `child_template_code`; contribute to fork-target index; do not require parent `run_kind=batch` long-term (compat: still accept legacy) |
| Seed | Do not add `run_kind` to **new** template recipes; leave existing seed keys for video v1 |

**Fork-target index:** For list performance, either:

- compute on read with a cached map `child_code → referrer_ids` from manageable set, or
- Phase 1.5 materialize `config.referenced_as_fork_target` only as cache (not source of truth).

Prefer on-read for correctness in Phase 1 (template counts are small).

### 4.4 Immutability contract (M-04)

Align product with schema:

- `update_template` continues to reject non-DRAFT for definition fields.
- UI must not offer paths that call it for ACTIVE.
- New `update_tags` is the **only** ACTIVE mutation besides `update_status` (archive) and schedule rows (separate table).

---

## 5. Implementation Plan (phased)

### Phase 1 — P0 / P1 (engine decouple + CRUD gaps)

**Goal:** Archive works end-to-end; tags replace type radio; gates stop depending on authoring `run_kind`; ACTIVE edit UX matches backend; list search/filter.

| Step | Work | Gaps |
|------|------|------|
| 1.1 | Frontend `archiveGraphTemplate` + list/designer Archive UI + confirm | M-01 |
| 1.2 | Manage list: status filter including archived; default unchanged | M-02 |
| 1.3 | DB `tags` + PATCH tags + schema fields; seed optional tags | M-03 (taxonomy) |
| 1.4 | Remove designer type radio; list column → tags + capability hints; dual-read instantiate gate | M-03 |
| 1.5 | `template_capabilities` + schedule/instantiate service switches; keep legacy fallback | M-03 |
| 1.6 | Disable ACTIVE save-settings/rename; banner + force fork-to-edit | M-04 |
| 1.7 | List `q` + status filter API/UI | M-05 |
| 1.8 | Optional: archive only from `active`; block when active schedules | M-01 hardening |
| 1.9 | Tests: capabilities matrix (blank / multi_instance / fork-child / legacy seeds); archive UI; list filters | — |

**Phase 1 exit:** Video v1 seeds still instantiate/fork/schedule as today; new blank template has no `run_kind` and is not mislabeled 批次/制作.

### Phase 2 — P2 (structured authoring)

| Step | Work | Gaps |
|------|------|------|
| 2.1 | Node inspector: `ui_profile` select + custom | M-06 |
| 2.2 | `context_schema` designer section | M-07 |
| 2.3 | Remaining F-26: `launch_schema` / routing form-ification | M-08 |
| 2.4 | Optional unarchive policy (sibling ACTIVE handling) | M-09 |
| 2.5 | Narrow dual-read; document deprecate `run_kind` projection | — |

### Explicit non-ordering

- Do not block Phase 1 on F-26 JSON cleanup.
- Do not remove seed `run_kind` keys in Phase 1.

---

## 6. Acceptance Criteria

### M-01 — Archive button + frontend API wrapper (P0)

- [ ] `workflow-graph.ts` exposes `archiveGraphTemplate(id)` calling `PATCH .../status` with `archived`.
- [ ] Manage list shows Archive for ACTIVE templates; confirm + success refresh.
- [ ] Designer shows Archive for ACTIVE; after archive, user leaves edit or sees read-only archived state.
- [ ] Draft continues to use Delete (not required to Archive).
- [ ] No new backend `/archive` route required.

### M-02 — Archived templates visible/filterable (P1)

- [ ] Manage list can show `status=archived` via filter/tab.
- [ ] Default view remains draft+active (no surprise empty “lost” templates without filter).
- [ ] Archived rows are clearly labeled; instantiate disabled.

### M-03 — Remove/downgrade template-level type; decouple instantiation (P1)

- [ ] Designer has **no** batch/production radio; saves do not write `run_kind` on new templates.
- [ ] List does not show 批次/制作 as system type; shows tags + capability hints.
- [ ] Direct instantiate uses capabilities (legacy `run_kind=production` still blocks via dual-read).
- [ ] `template_is_schedulable` does not require `run_kind=batch`.
- [ ] Legacy seeds keep `config.run_kind` readable; video v1 E2E paths still pass.
- [ ] Tags have no effect on instantiate/schedule/fork.

### M-04 — Active save settings / rename vs immutability (P1)

- [ ] ACTIVE/ARCHIVED: UI disables in-place save of name/description/config/graph.
- [ ] User is directed to fork/new version to edit definition.
- [ ] ACTIVE may still update **tags only** (and archive via status).
- [ ] Calling definition PATCH on ACTIVE still returns conflict (backend unchanged or clearer message).

### M-05 — List search + status filter (P1)

- [ ] Search by name and code (substring).
- [ ] Status filter includes at least draft / active / archived / (default combined).
- [ ] Filters compose (search within selected statuses).

### M-06 — Node `ui_profile` structured authoring (P2)

- [ ] Selected node can set `ui_profile` without raw JSON for common values.
- [ ] Custom/advanced JSON still available.
- [ ] UI copy does not present `ui_profile` as template type.

### M-07 — `context_schema` designer entry (P2)

- [ ] Designer exposes create/edit/view of `context_schema` (structured and/or JSON).
- [ ] Values persist on draft save and appear in designer detail API.

### M-08 — launch_schema / routing form-ification (P2, F-26)

- [ ] Common `launch_schema` fields editable via form controls.
- [ ] Common routing rules editable without mandatory JSON.
- [ ] JSON escape hatch retained for power users.

### M-09 — Unarchive (P2, optional)

- [ ] If implemented: `archived → active` enforces single ACTIVE per `base_code` (archive siblings), same as publish.

### Cross-cutting

- [ ] Spec constraints honored: no behavioral dependency on user tags; engine remains vertical-agnostic.
- [ ] Backward compatible: legacy video v1 templates continue to work under dual-read.
- [ ] Memory-bank contracts/docs updated in the **implementation** session (not required to edit other files in design-only delivery).

---

## Appendix A — Capability matrix (examples)

| Template shape | Tags (example) | has_launch_entry | has_multi_instance | launch_schema | is_fork_target | can_instantiate_directly | can_schedule (if schedulable=true, non-streaming) |
|----------------|----------------|------------------|--------------------|---------------|----------------|--------------------------|--------------------------------------------------|
| Blank draft with 1 start task node | [] | yes | no | no | no | no (not active) / yes when active | no |
| Video batch seed | [视频,选题会] | yes | yes | yes | no | yes | yes |
| Video production seed | [视频,制作] | yes | no* | no | yes | **no** (`is_fork_only`) | no |
| Collector + schedulable | [周会] | yes | yes | yes | no | yes | yes |
| Fork child with launch_schema added | [] | yes | no | yes | yes | **yes** (has launch surface) | no |

\*production seed nodes are typically `kind=single`; matrix focuses on gates, not video node count.

## Appendix B — File touch map (implementation later)

| Area | Likely files |
|------|----------------|
| FE API | `frontend/src/api/workflow-graph.ts` |
| FE list/designer | `GraphTemplatesPanel.vue`, `GraphTemplateDesignerView.vue`, `GraphTemplateEditDialog.vue`, `TaskTemplatesView.vue` |
| FE gate | `frontend/src/utils/workflowVideoSchema.ts` |
| BE admin/schedule | `workflow_graph_template_admin_service.py`, `workflow_graph_template_schedule_service.py` |
| BE instantiate/fork | `workflow_video_instantiation_service.py`, `workflow_video_fork_service.py` |
| Schemas/routes | `schemas/workflow_graph.py`, `api/routes/workflow_graph_engine.py` |
| ORM/migration | `models/workflow_graph.py`, new Alembic revision |

## Appendix C — Open questions (resolve in Phase 1 kickoff)

1. **Tag vocabulary:** free-form only vs shared suggestion list from existing tags?
2. **Fork match key:** exact `code` only vs `base_code` for “any version of production template”?
3. **ACTIVE tag edits:** confirm product OK (recommended yes).
4. **Archive with active schedules:** hard-block vs auto-disable schedules?

**Recommendation defaults:** free-form + suggestions; match `code` then `base_code`; allow ACTIVE tag edits; hard-block archive while ACTIVE schedules exist (force disable first).
