---
type: paradigma-plan
title: "Template Engine Decouple — Phase 1 Implementation Plan"
description: "Bite-sized tasks for M-01–M-05: archive UI, tags, type removal, ACTIVE edit contract, search/filter."
tags: ["plan", "workflow-graph", "template-engine", "phase-1", "tags", "capabilities"]
timestamp: 2026-07-22T15:30:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  retrieval_hints:
    zh: ["模板引擎解耦", "Phase 1", "tags", "capabilities", "归档", "M-01"]
    en: ["template decouple", "phase 1", "tags", "capabilities", "archive"]
---

# Goal

Ship Phase 1 of ADR-017 / spec §5.1: archive works end-to-end; user **tags** replace the batch/production type radio; runtime gates use **TemplateCapabilities** (dual-read legacy `run_kind`); ACTIVE templates cannot be edited in-place except tags + archive; manage list supports status filter and `q` search.

# Scope

| In (M-01–M-05) | Out (Phase 2+) |
|----------------|----------------|
| `tags` column + PATCH tags API | `ui_profile` structured editor (M-06) |
| `template_capabilities` + schedule/instantiate switches | `context_schema` designer (M-07) |
| Archive UI (list + designer) + schedule guard | launch_schema form-ification (M-08) |
| Status filter + search (`q`) | unarchive (M-09) |
| Remove type radio; list shows tags + capability hints | Remove seed `run_kind` keys |
| Disable ACTIVE save-settings / rename; fork-to-edit banner | GIN index on tags (Phase 1.5) |

**Spec mapping:** 1.1 M-01 · 1.2 M-02 · 1.3 M-03 taxonomy · 1.4 M-03 UI · 1.5 M-03 gates · 1.6 M-04 · 1.7 M-05 · 1.8 M-01 hardening · 1.9 tests

# Approach

1. **Backend first:** Alembic `tags` → ORM/schemas → pure `template_capabilities` → admin list filters + tags PATCH → archive guard → `template_is_schedulable` / instantiate gate.
2. **Frontend API:** `archiveGraphTemplate`, `updateGraphTemplateTags`, extend `listGraphTemplates`.
3. **Frontend UI:** list filters/search/archive → designer tag editor + capabilities readout + archive → remove type radio → disable ACTIVE definition edits.
4. **Tests last:** capabilities matrix, archive UI, list filters, dual-read instantiate helper.

# Tasks

---

## Backend

### Task B1 — Alembic: add `tags` column

**File:** `backend/alembic/versions/20260722_01_workflow_graph_template_tags.py`  
**Estimated time:** 3 minutes

```python
"""Add workflow_graph_templates.tags JSONB column.

Revision ID: 20260722_01
Revises: 20260717_02
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260722_01"
down_revision = "20260717_02"
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
  return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
  op.add_column(
    "workflow_graph_templates",
    sa.Column(
      "tags",
      _json_type(),
      nullable=False,
      server_default=sa.text("'[]'"),
    ),
  )
  op.execute(
    """
    UPDATE workflow_graph_templates
    SET tags = '["视频", "选题会"]'::jsonb
    WHERE code LIKE 'topic_meeting_batch%'
    """
  )
  op.execute(
    """
    UPDATE workflow_graph_templates
    SET tags = '["视频", "制作"]'::jsonb
    WHERE code LIKE 'video_production_per_topic%'
    """
  )


def downgrade() -> None:
  op.drop_column("workflow_graph_templates", "tags")
```

### Verification

```bash
cd backend && alembic upgrade head
```

Expected output ends with: `Running upgrade 20260717_02 -> 20260722_01`

```bash
cd backend && python -c "
from sqlalchemy import create_engine, text
from app.core.config import Settings
engine = create_engine(Settings().sync_database_url)
with engine.connect() as conn:
  row = conn.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='workflow_graph_templates' AND column_name='tags'\")).fetchone()
  print('tags column:', row is not None)
"
```

Expected: `tags column: True`

---

### Task B2 — ORM: `WorkflowGraphTemplate.tags`

**File:** `backend/app/models/workflow_graph.py`  
**Insert after:** `config` column (~line 56)  
**Estimated time:** 2 minutes

```python
  tags: Mapped[list[Any]] = mapped_column(build_json_type(), default=list, nullable=False)
```

### Verification

```bash
cd backend && python -c "from app.models import WorkflowGraphTemplate; assert 'tags' in WorkflowGraphTemplate.__table__.columns; print('ok')"
```

Expected: `ok`

---

### Task B3 — Schemas: `TemplateCapabilitiesRead` + `tags` on summary/detail

**File:** `backend/app/schemas/workflow_graph.py`  
**Insert after:** `WorkflowGraphTemplateSummaryRead` fields (~line 38)  
**Estimated time:** 4 minutes

```python
class TemplateCapabilitiesRead(BaseModel):
  can_instantiate_directly: bool = False
  can_schedule: bool = False
  is_fork_target: bool = False
  has_multi_instance: bool = False
  has_launch_entry: bool = False
  derived_hints: list[str] = Field(default_factory=list)


class WorkflowGraphTemplateTagsUpdateRequest(BaseModel):
  tags: list[str] = Field(default_factory=list, max_length=32)


```

Add to `WorkflowGraphTemplateSummaryRead` (after `run_kind`):

```python
  tags: list[str] = Field(default_factory=list)
  capabilities: TemplateCapabilitiesRead = Field(default_factory=TemplateCapabilitiesRead)
```

Mark deprecated on `run_kind` field:

```python
  run_kind: str | None = Field(
    default=None,
    description="Deprecated: legacy video v1 product type from config.run_kind. Use capabilities.",
  )
```

### Verification

```bash
cd backend && python -c "
from app.schemas.workflow_graph import TemplateCapabilitiesRead, WorkflowGraphTemplateSummaryRead
m = WorkflowGraphTemplateSummaryRead.model_validate({
  'id': '00000000-0000-0000-0000-000000000001',
  'code': 'x', 'name': 'x', 'status': 'draft', 'version': 1,
})
assert m.capabilities.can_instantiate_directly is False
assert m.tags == []
print('ok')
"
```

Expected: `ok`

---

### Task B4 — Service: `template_capabilities` pure function

**File:** `backend/app/services/workflow_graph_template_capabilities.py` (new)  
**Estimated time:** 5 minutes

```python
"""Derive TemplateCapabilities from graph structure + explicit opt-in flags (ADR-017)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode


@dataclass(frozen=True, slots=True)
class TemplateCapabilities:
  can_instantiate_directly: bool
  can_schedule: bool
  is_fork_target: bool
  has_multi_instance: bool
  has_launch_entry: bool
  derived_hints: list[str]


def normalize_template_tags(raw: list[str] | None) -> list[str]:
  seen: set[str] = set()
  normalized: list[str] = []
  for item in raw or []:
    tag = str(item).strip()
    if not tag or tag in seen:
      continue
    seen.add(tag)
    normalized.append(tag)
  return normalized


def _has_multi_instance(nodes: list[WorkflowGraphTemplateNode]) -> bool:
  return any(
    isinstance(node.config, dict)
    and node.config.get("kind") == "multi_instance"
    and node.config.get("expand_from")
    for node in nodes
  )


def _has_launch_entry(
  nodes: list[WorkflowGraphTemplateNode],
  edges: list[WorkflowGraphTemplateEdge],
) -> bool:
  if not nodes:
    return False
  id_to_key = {node.id: node.node_key for node in nodes}
  incoming: dict[str, int] = {node.node_key: 0 for node in nodes}
  for edge in edges:
    if edge.is_reject_path:
      continue
    to_key = id_to_key.get(edge.to_node_id)
    if to_key in incoming:
      incoming[to_key] += 1
  return any(degree == 0 for degree in incoming.values())


def _has_direct_launch_surface(config: dict[str, Any], *, has_multi_instance: bool) -> bool:
  launch_schema = config.get("launch_schema")
  has_launch_schema = isinstance(launch_schema, (dict, list)) and bool(launch_schema)
  return has_launch_schema or config.get("schedulable") is True or has_multi_instance


def _legacy_blocks_direct_instantiation(config: dict[str, Any]) -> bool:
  return str(config.get("run_kind") or "") == "production"


def compute_template_capabilities(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
  edges: list[WorkflowGraphTemplateEdge],
  fork_target_codes: set[str],
) -> TemplateCapabilities:
  config = template.config if isinstance(template.config, dict) else {}
  template_code = str(template.code or "")
  template_base = str(template.base_code or "")
  has_mi = _has_multi_instance(nodes)
  has_entry = _has_launch_entry(nodes, edges)
  is_fork_target = template_code in fork_target_codes or template_base in fork_target_codes
  has_surface = _has_direct_launch_surface(config, has_multi_instance=has_mi)
  is_fork_only = is_fork_target and not has_surface

  can_instantiate = (
    template.status == WorkflowGraphTemplateStatus.ACTIVE
    and has_entry
    and not is_fork_only
  )
  if _legacy_blocks_direct_instantiation(config):
    can_instantiate = False

  can_schedule = (
    config.get("schedulable") is True
    and has_mi
    and can_instantiate
    and config.get("aggregate_mode") != "streaming"
  )

  hints: list[str] = []
  if can_instantiate:
    hints.append("可直接发起")
  if can_schedule:
    hints.append("可调度")
  if is_fork_target:
    hints.append("可作为子流程目标")
  if is_fork_only:
    hints.append("仅子流程")

  return TemplateCapabilities(
    can_instantiate_directly=can_instantiate,
    can_schedule=can_schedule,
    is_fork_target=is_fork_target,
    has_multi_instance=has_mi,
    has_launch_entry=has_entry,
    derived_hints=hints,
  )


def build_fork_target_code_index(templates: list[WorkflowGraphTemplate]) -> set[str]:
  codes: set[str] = set()
  for template in templates:
    config = template.config if isinstance(template.config, dict) else {}
    child_code = config.get("child_template_code")
    if isinstance(child_code, str) and child_code.strip():
      codes.add(child_code.strip())
  return codes
```

### Verification

```bash
cd backend && python -c "from app.services.workflow_graph_template_capabilities import compute_template_capabilities; print('ok')"
```

Expected: `ok`

---

### Task B5 — Test: capabilities matrix

**File:** `backend/tests/test_workflow_graph_template_capabilities.py` (new)  
**Estimated time:** 5 minutes

```python
"""TemplateCapabilities matrix (spec Appendix A)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateEdge, WorkflowGraphTemplateNode
from app.services.workflow_graph_template_capabilities import compute_template_capabilities


def _template(*, status: WorkflowGraphTemplateStatus, config: dict) -> WorkflowGraphTemplate:
  return WorkflowGraphTemplate(
    id=uuid4(),
    code="test_tpl_v1",
    base_code="test_tpl",
    version=1,
    name="Test",
    status=status,
    config=config,
    created_by=uuid4(),
  )


def _start_node() -> WorkflowGraphTemplateNode:
  node = WorkflowGraphTemplateNode(
    id=uuid4(),
    template_id=uuid4(),
    node_key="N1_START",
    title="Start",
    sort_order=1,
    config={"kind": "single"},
  )
  return node


@pytest.mark.parametrize(
  ("status", "config", "node_config", "fork_codes", "expect_direct", "expect_schedule"),
  [
    (
      WorkflowGraphTemplateStatus.DRAFT,
      {},
      {"kind": "single"},
      set(),
      False,
      False,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"schedulable": True, "launch_schema": {"fields": []}, "aggregate_mode": "batch"},
      {"kind": "multi_instance", "expand_from": "copywriters"},
      set(),
      True,
      True,
    ),
    (
      WorkflowGraphTemplateStatus.ACTIVE,
      {"run_kind": "production"},
      {"kind": "single"},
      {"test_tpl_v1"},
      False,
      False,
    ),
  ],
)
def test_capabilities_matrix(
  status,
  config,
  node_config,
  fork_codes,
  expect_direct,
  expect_schedule,
) -> None:
  template = _template(status=status, config=config)
  node = _start_node()
  node.config = node_config
  caps = compute_template_capabilities(
    template=template,
    nodes=[node],
    edges=[],
    fork_target_codes=fork_codes,
  )
  assert caps.can_instantiate_directly is expect_direct
  assert caps.can_schedule is expect_schedule
```

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_graph_template_capabilities.py -x -q
```

Expected output contains: `3 passed`

---

### Task B6 — `template_is_schedulable`: drop `run_kind == batch`

**File:** `backend/app/services/workflow_graph_template_schedule_service.py`  
**Replace:** `template_is_schedulable` function (lines 50–71)  
**Estimated time:** 3 minutes

```python
def template_is_schedulable(
  *,
  template: WorkflowGraphTemplate,
  nodes: list[WorkflowGraphTemplateNode],
) -> bool:
  from app.services.workflow_graph_template_capabilities import compute_template_capabilities

  caps = compute_template_capabilities(
    template=template,
    nodes=nodes,
    edges=[],
    fork_target_codes=set(),
  )
  return caps.can_schedule
```

### Verification

```bash
cd backend && python -m pytest tests/test_f24_graph_template_schedules.py -x -q
```

Expected: all tests pass (schedulable seed still has `schedulable=True` + multi_instance).

---

### Task B7 — Admin: `list_manageable_templates(status_filter, q)`

**File:** `backend/app/services/workflow_graph_template_admin_service.py`  
**Replace:** `list_manageable_templates` (lines 92–103)  
**Estimated time:** 4 minutes

Add imports at top:

```python
from sqlalchemy import or_

from app.core.enums import WorkflowGraphTemplateStatus
from app.services.workflow_graph_template_capabilities import normalize_template_tags
```

Replace method:

```python
  async def list_manageable_templates(
    self,
    *,
    status_filter: list[WorkflowGraphTemplateStatus] | None = None,
    q: str | None = None,
  ) -> list[WorkflowGraphTemplate]:
    statuses = status_filter or [
      WorkflowGraphTemplateStatus.DRAFT,
      WorkflowGraphTemplateStatus.ACTIVE,
    ]
    stmt = (
      select(WorkflowGraphTemplate)
      .where(WorkflowGraphTemplate.status.in_(statuses))
      .order_by(WorkflowGraphTemplate.base_code.asc(), WorkflowGraphTemplate.version.desc())
    )
    needle = (q or "").strip()
    if needle:
      pattern = f"%{needle}%"
      stmt = stmt.where(
        or_(
          WorkflowGraphTemplate.name.ilike(pattern),
          WorkflowGraphTemplate.code.ilike(pattern),
        )
      )
    return list(await self._session.scalars(stmt))
```

### Verification

```bash
cd backend && python -c "
import asyncio
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
print('import ok')
"
```

Expected: `import ok`

---

### Task B8 — Route: `status` + `q` query params on manage list

**File:** `backend/app/api/routes/workflow_graph_engine.py`  
**Estimated time:** 4 minutes

Add import:

```python
from app.core.enums import WorkflowGraphTemplateStatus
from app.schemas.workflow_graph import TemplateCapabilitiesRead
from app.services.workflow_graph_template_capabilities import (
  build_fork_target_code_index,
  compute_template_capabilities,
)
```

Extend `list_graph_templates` signature (~line 264):

```python
async def list_graph_templates(
  actor: Annotated[User, Depends(get_current_user)],
  session: Annotated[AsyncSession, Depends(get_db_session)],
  workflow_graph_service: Annotated[WorkflowGraphService, Depends(get_workflow_graph_service)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
  scope: Annotated[str | None, Query()] = None,
  schedulable: Annotated[bool | None, Query()] = None,
  status: Annotated[list[WorkflowGraphTemplateStatus] | None, Query()] = None,
  q: Annotated[str | None, Query(max_length=120)] = None,
) -> list[WorkflowGraphTemplateSummaryRead]:
```

Replace manage branch:

```python
  if scope == "manage" and await can_manage_task_templates(session, actor):
    templates = await admin_service.list_manageable_templates(status_filter=status, q=q)
    stats_map = await admin_service.load_template_stats_map(template_ids=[template.id for template in templates])
    fork_codes = build_fork_target_code_index(templates)
```

In response builder loop, load nodes/edges and attach capabilities:

```python
  fork_codes = build_fork_target_code_index(templates) if scope == "manage" else set()
  results: list[WorkflowGraphTemplateSummaryRead] = []
  for template in templates:
    nodes = list(
      await session.scalars(
        select(WorkflowGraphTemplateNode).where(WorkflowGraphTemplateNode.template_id == template.id)
      )
    )
    edges = list(
      await session.scalars(
        select(WorkflowGraphTemplateEdge).where(WorkflowGraphTemplateEdge.template_id == template.id)
      )
    )
    caps = compute_template_capabilities(
      template=template,
      nodes=nodes,
      edges=edges,
      fork_target_codes=fork_codes,
    )
    config = dict(template.config or {})
    results.append(
      WorkflowGraphTemplateSummaryRead(
        id=template.id,
        code=template.code,
        name=template.name,
        description=template.description,
        status=template.status,
        version=template.version,
        run_kind=str(config.get("run_kind") or "") or None,
        tags=[str(tag) for tag in (template.tags or [])],
        capabilities=TemplateCapabilitiesRead(
          can_instantiate_directly=caps.can_instantiate_directly,
          can_schedule=caps.can_schedule,
          is_fork_target=caps.is_fork_target,
          has_multi_instance=caps.has_multi_instance,
          has_launch_entry=caps.has_launch_entry,
          derived_hints=caps.derived_hints,
        ),
        config=config,
        scope_mode=template.scope_mode,
        scope_department_ids=[str(did) for did in (template.scope_department_ids or [])],
        run_count_total=stats_map[template.id].run_count_total if template.id in stats_map else None,
        run_count_30d=stats_map[template.id].run_count_30d if template.id in stats_map else None,
        active_run_count=stats_map[template.id].active_run_count if template.id in stats_map else None,
      )
    )
  return results
```

Remove the old inline `return [...]` list comprehension.

### Verification

```bash
cd backend && python -m pytest tests/test_api.py -k "graph_template" -x -q 2>/dev/null | tail -3
```

Expected: no import/syntax errors (individual API tests may need fixture updates in B15).

---

### Task B9 — Admin: `update_tags` + PATCH route

**File:** `backend/app/services/workflow_graph_template_admin_service.py`  
**Insert after:** `update_template` (~line 243)  
**Estimated time:** 3 minutes

```python
  async def update_tags(
    self,
    *,
    actor: User,
    template_id: UUID,
    tags: list[str],
  ) -> WorkflowGraphTemplateDetailRead:
    await self._ensure_manage(actor)
    template = await self._get_template_or_raise(template_id=template_id)
    if template.status == WorkflowGraphTemplateStatus.ARCHIVED:
      raise ConflictError("已归档模板不可修改标签。")
    template.tags = normalize_template_tags(tags)
    await self._session.flush()
    result = await self.get_template_detail(template_id=template_id)
    await self._commit()
    return result
```

**File:** `backend/app/api/routes/workflow_graph_engine.py`  
**Insert after:** `update_graph_template` route (~line 507)

```python
@router.patch(
  "/templates/{template_id}/tags",
  response_model=WorkflowGraphTemplateDetailRead,
  tags=["workflow-graph"],
)
async def update_graph_template_tags(
  template_id: UUID,
  payload: WorkflowGraphTemplateTagsUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  admin_service: Annotated[WorkflowGraphTemplateAdminService, Depends(get_workflow_graph_template_admin_service)],
) -> WorkflowGraphTemplateDetailRead:
  return await admin_service.update_tags(
    actor=actor,
    template_id=template_id,
    tags=payload.tags,
  )
```

Add import for `WorkflowGraphTemplateTagsUpdateRequest`.

Wire `tags` into `_build_detail_read` / `_build_designer_read`:

```python
      tags=[str(tag) for tag in (template.tags or [])],
      capabilities=TemplateCapabilitiesRead(...),  # compute inline same as list route
```

### Verification

```bash
cd backend && python -c "from app.api.routes.workflow_graph_engine import update_graph_template_tags; print('ok')"
```

Expected: `ok`

---

### Task B10 — Test: tags PATCH + ACTIVE allowed

**File:** `backend/tests/test_workflow_graph_template_tags.py` (new)  
**Estimated time:** 4 minutes

```python
import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.core.exceptions import ConflictError
from app.schemas.workflow_graph import WorkflowGraphTemplateStatusUpdateRequest
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from test_workflow_graph_template_designer_d1 import _seed_batch_template


@pytest.mark.asyncio
async def test_active_template_tags_patch(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_tags(actor=admin, template_id=source.id, tags=["视频", "周会"])
  detail = await service.get_template_detail(template_id=source.id)
  assert detail.tags == ["视频", "周会"]


@pytest.mark.asyncio
async def test_archived_template_tags_rejected(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_status(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ARCHIVED),
  )
  with pytest.raises(ConflictError, match="已归档"):
    await service.update_tags(actor=admin, template_id=source.id, tags=["x"])
```

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_graph_template_tags.py -x -v
```

Expected: `2 passed`

---

### Task B11 — Archive guard: active-only + active schedule block

**File:** `backend/app/services/workflow_graph_template_admin_service.py`  
**Replace:** `update_status` archived branch (lines 281–282)  
**Estimated time:** 4 minutes

Add import:

```python
from app.models import WorkflowGraphTemplateSchedule
```

Replace archived handling:

```python
    elif target_status == WorkflowGraphTemplateStatus.ARCHIVED:
      if template.status != WorkflowGraphTemplateStatus.ACTIVE:
        raise ConflictError("仅已发布（active）模板可归档；草稿请使用删除。")
      active_schedule_count = await self._session.scalar(
        select(func.count())
        .select_from(WorkflowGraphTemplateSchedule)
        .where(
          WorkflowGraphTemplateSchedule.template_id == template.id,
          WorkflowGraphTemplateSchedule.is_active.is_(True),
        )
      )
      if active_schedule_count and int(active_schedule_count) > 0:
        raise ConflictError("模板仍有启用的周期调度，请先停用调度后再归档。")
      template.status = WorkflowGraphTemplateStatus.ARCHIVED
```

Add `from sqlalchemy import func, select` if missing.

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_graph_template_designer_d1.py::test_d1_validate_and_publish -x -v
```

Expected: `PASSED`

---

### Task B12 — Stop writing `run_kind` on blank create + strip on draft save

**File:** `backend/app/services/workflow_graph_template_admin_service.py`  
**Estimated time:** 3 minutes

In `_create_blank_template` (~line 595), replace config:

```python
      config={"aggregate_mode": "streaming"},
```

In `save_draft`, after `template.config = dict(payload.config or {})`:

```python
    if "run_kind" not in dict(source.config or {}) if False else "run_kind" not in dict(template.config or {}):
      template.config.pop("run_kind", None)
```

Cleaner version — add helper and call in `save_draft`:

```python
  @staticmethod
  def _strip_run_kind_unless_legacy(*, existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = {**existing, **incoming}
    if "run_kind" not in existing:
      merged.pop("run_kind", None)
    return merged
```

In `save_draft`:

```python
    template.config = self._strip_run_kind_unless_legacy(
      existing=dict(template.config or {}),
      incoming=dict(payload.config or {}),
    )
```

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_graph_template_designer_d1.py -x -q
```

Expected: all pass; new blank templates no longer default `run_kind=batch`.

---

### Task B13 — Instantiate gate via capabilities

**File:** `backend/app/services/workflow_video_instantiation_service.py`  
**Insert in:** `instantiate_graph_template` after `_load_template_graph` (~line 369)  
**Estimated time:** 3 minutes

```python
    from app.services.workflow_graph_template_capabilities import compute_template_capabilities

    caps = compute_template_capabilities(
      template=template,
      nodes=nodes,
      edges=edges,
      fork_target_codes=set(),
    )
    if not caps.can_instantiate_directly:
      raise ConflictError("该模板不支持直接实例化。")
```

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_video_w3_instantiation.py -x -q
```

Expected: batch seed tests pass; production direct instantiate (if tested) returns 409.

---

### Task B14 — Test: manage list status + q filters

**File:** `backend/tests/test_workflow_graph_template_list_filters.py` (new)  
**Estimated time:** 5 minutes

```python
import pytest

from app.core.enums import WorkflowGraphTemplateStatus
from app.schemas.workflow_graph import WorkflowGraphTemplateStatusUpdateRequest
from app.services.workflow_graph_template_admin_service import WorkflowGraphTemplateAdminService
from test_workflow_graph_template_designer_d1 import _seed_batch_template


@pytest.mark.asyncio
async def test_list_includes_archived_when_requested(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  await service.update_status(
    actor=admin,
    template_id=source.id,
    payload=WorkflowGraphTemplateStatusUpdateRequest(status=WorkflowGraphTemplateStatus.ARCHIVED),
  )
  default_list = await service.list_manageable_templates()
  assert all(t.status != WorkflowGraphTemplateStatus.ARCHIVED for t in default_list)
  with_archived = await service.list_manageable_templates(
    status_filter=[
      WorkflowGraphTemplateStatus.DRAFT,
      WorkflowGraphTemplateStatus.ACTIVE,
      WorkflowGraphTemplateStatus.ARCHIVED,
    ],
  )
  assert any(t.id == source.id and t.status == WorkflowGraphTemplateStatus.ARCHIVED for t in with_archived)


@pytest.mark.asyncio
async def test_list_q_matches_name_or_code(db_session) -> None:
  admin, source = await _seed_batch_template(db_session)
  service = WorkflowGraphTemplateAdminService(db_session)
  hits = await service.list_manageable_templates(q="topic_meeting")
  assert any(t.id == source.id for t in hits)
  misses = await service.list_manageable_templates(q="zzzz-no-match-zzzz")
  assert not any(t.id == source.id for t in misses)
```

### Verification

```bash
cd backend && python -m pytest tests/test_workflow_graph_template_list_filters.py tests/test_workflow_graph_template_capabilities.py tests/test_workflow_graph_template_tags.py -x -q
```

Expected: `7 passed`

---

## Frontend API

### Task F1 — `archiveGraphTemplate` + `updateGraphTemplateTags`

**File:** `frontend/src/api/workflow-graph.ts`  
**Insert after:** `publishGraphTemplate` (~line 229)  
**Estimated time:** 3 minutes

```typescript
export async function archiveGraphTemplate(templateId: string): Promise<GraphTemplateDesignerDetail> {
  const { data } = await http.patch<GraphTemplateDesignerDetail>(
    `/workflow-graph/templates/${templateId}/status`,
    { status: 'archived' },
  )
  return {
    ...data,
    config: data.config ?? {},
    nodes: data.nodes ?? [],
    edges: data.edges ?? [],
  }
}

export async function updateGraphTemplateTags(
  templateId: string,
  tags: string[],
): Promise<GraphTemplateDetail> {
  const { data } = await http.patch<GraphTemplateDetail>(`/workflow-graph/templates/${templateId}/tags`, {
    tags,
  })
  return {
    ...data,
    config: data.config ?? {},
  }
}
```

### Verification

```bash
cd frontend && npm run test:unit -- workflowVideoW7Api.spec.ts -x 2>&1 | tail -5
```

Expected: vitest completes without TS compile errors on `workflow-graph.ts`.

---

### Task F2 — Extend `listGraphTemplates` with `status` + `q`

**File:** `frontend/src/api/workflow-graph.ts`  
**Replace:** `listGraphTemplates` options (~line 76)  
**Estimated time:** 2 minutes

```typescript
export async function listGraphTemplates(options?: {
  manage?: boolean
  schedulable?: boolean
  status?: Array<'draft' | 'active' | 'archived'>
  q?: string
}): Promise<GraphTemplateSummary[]> {
  const { data } = await http.get<
    Array<Omit<GraphTemplateSummary, 'config'> & { config?: Record<string, unknown> }>
  >('/workflow-graph/templates', {
    params: {
      ...(options?.manage ? { scope: 'manage' } : {}),
      ...(options?.schedulable ? { schedulable: true } : {}),
      ...(options?.status?.length ? { status: options.status } : {}),
      ...(options?.q?.trim() ? { q: options.q.trim() } : {}),
    },
  })
  return data.map((item) => ({
    ...item,
    config: item.config ?? {},
  }))
}
```

### Verification

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep workflow-graph || echo "no workflow-graph errors"
```

Expected: `no workflow-graph errors`

---

### Task F3 — Types: `TemplateCapabilities` + extend summary

**File:** `frontend/src/types/workflowVideo.ts`  
**Insert before:** `GraphTemplateSummary` (~line 175)  
**Estimated time:** 2 minutes

```typescript
export interface TemplateCapabilities {
  can_instantiate_directly: boolean
  can_schedule: boolean
  is_fork_target: boolean
  has_multi_instance: boolean
  has_launch_entry: boolean
  derived_hints: string[]
}
```

Add to `GraphTemplateSummary`:

```typescript
  tags?: string[]
  capabilities?: TemplateCapabilities
```

### Verification

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep workflowVideo || echo "ok"
```

Expected: `ok`

---

## Frontend UI

### Task FE1 — `templateSupportsDirectInstantiation` dual-read

**File:** `frontend/src/utils/workflowVideoSchema.ts`  
**Replace:** `templateSupportsDirectInstantiation` (~lines 109–118)  
**Estimated time:** 2 minutes

```typescript
export function templateSupportsDirectInstantiation(
  template:
    | {
        run_kind?: string | null
        config?: Record<string, unknown>
        capabilities?: { can_instantiate_directly?: boolean }
      }
    | null
    | undefined,
): boolean {
  if (!template) {
    return false
  }
  if (template.capabilities && typeof template.capabilities.can_instantiate_directly === 'boolean') {
    return template.capabilities.can_instantiate_directly
  }
  if (template.run_kind === 'production') {
    return false
  }
  return template.status === 'active' || template.status === undefined
}
```

**File:** `frontend/tests/workflowVideoSchema.spec.ts` — append:

```typescript
import { templateSupportsDirectInstantiation } from '@/utils/workflowVideoSchema'

describe('templateSupportsDirectInstantiation', () => {
  it('prefers capabilities over legacy run_kind', () => {
    expect(
      templateSupportsDirectInstantiation({
        run_kind: 'production',
        status: 'active',
        capabilities: { can_instantiate_directly: true },
      }),
    ).toBe(true)
  })

  it('falls back to run_kind=production block', () => {
    expect(templateSupportsDirectInstantiation({ run_kind: 'production', status: 'active' })).toBe(false)
  })
})
```

### Verification

```bash
cd frontend && npm run test:unit -- workflowVideoSchema.spec.ts -x
```

Expected: all tests `PASS`

---

### Task FE2 — GraphTemplatesPanel: status filter + search + load params

**File:** `frontend/src/components/workflow/GraphTemplatesPanel.vue`  
**Estimated time:** 5 minutes

Add refs after `loading`:

```typescript
const statusFilter = ref<'working' | 'all' | 'archived'>('working')
const searchQuery = ref('')

const listStatusParam = computed((): Array<'draft' | 'active' | 'archived'> | undefined => {
  if (statusFilter.value === 'all') {
    return ['draft', 'active', 'archived']
  }
  if (statusFilter.value === 'archived') {
    return ['archived']
  }
  return ['draft', 'active']
})
```

Replace `loadTemplates`:

```typescript
async function loadTemplates(): Promise<void> {
  loading.value = true
  try {
    templates.value = await listGraphTemplates({
      manage: props.canManage,
      status: listStatusParam.value,
      q: searchQuery.value,
    })
    if (!selectedTemplate.value && templates.value.length > 0) {
      selectedTemplate.value = templates.value[0] ?? null
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    templates.value = []
  } finally {
    loading.value = false
  }
}
```

In template header (inside `graph-templates__header`), before refresh button:

```html
          <el-select v-model="statusFilter" style="width: 140px" data-testid="graph-template-status-filter" @change="loadTemplates">
            <el-option label="草稿+已发布" value="working" />
            <el-option label="全部" value="all" />
            <el-option label="已归档" value="archived" />
          </el-select>
          <el-input
            v-model="searchQuery"
            clearable
            placeholder="搜索名称或编码"
            style="width: 200px"
            data-testid="graph-template-search"
            @clear="loadTemplates"
            @keyup.enter="loadTemplates"
          />
```

### Verification

Manual smoke: open Task Templates → change filter → list reloads.

---

### Task FE3 — GraphTemplatesPanel: archive action

**File:** `frontend/src/components/workflow/GraphTemplatesPanel.vue`  
**Estimated time:** 4 minutes

Add import:

```typescript
import { archiveGraphTemplate, cloneGraphTemplate, createBlankGraphTemplate, deleteGraphTemplate, listGraphTemplates } from '@/api/workflow-graph'
```

Add handler:

```typescript
async function handleArchive(template: GraphTemplateSummary): Promise<void> {
  if (!props.canManage || template.status !== 'active') {
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认归档「${template.name}」？归档后不可原地编辑；可在列表中筛选查看。`,
      '归档任务模板',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
    await archiveGraphTemplate(template.id)
    ElMessage.success('模板已归档')
    await loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(getErrorMessage(error))
    }
  }
}
```

In actions column, after 设计 button:

```html
            <el-button
              v-if="canManage && row.status === 'active'"
              link
              type="warning"
              data-testid="graph-template-archive"
              @click.stop="handleArchive(row)"
            >
              归档
            </el-button>
```

Restrict delete to draft only:

```html
            <el-button
              v-else-if="canManage && row.status === 'draft'"
              link
              type="danger"
              data-testid="graph-template-delete"
              @click.stop="handleDelete(row)"
            >
              删除
            </el-button>
```

### Verification

```bash
cd frontend && npm run test:unit -- GraphTemplatesPanel.spec.ts -x 2>&1 | tail -8
```

(Create spec in FE-T1 if missing.)

---

### Task FE4 — GraphTemplatesPanel: tags + capability hints column

**File:** `frontend/src/components/workflow/GraphTemplatesPanel.vue`  
**Replace:** 类型 column (~lines 206–212)  
**Estimated time:** 3 minutes

```html
        <el-table-column label="标签 / 能力" min-width="200">
          <template #default="{ row }: { row: GraphTemplateSummary }">
            <el-tag
              v-for="tag in row.tags ?? []"
              :key="tag"
              size="small"
              effect="plain"
              class="graph-templates__tag"
            >
              {{ tag }}
            </el-tag>
            <el-tag
              v-for="hint in row.capabilities?.derived_hints ?? []"
              :key="hint"
              size="small"
              type="info"
              effect="plain"
            >
              {{ hint }}
            </el-tag>
            <span v-if="!(row.tags?.length) && !(row.capabilities?.derived_hints?.length)">—</span>
          </template>
        </el-table-column>
```

Replace production-only instantiate tooltip with capabilities check:

```html
            <el-tooltip
              v-if="!canInstantiateTemplate(row)"
              :content="row.capabilities?.derived_hints?.includes('仅子流程') ? '仅子流程模板，不支持直接实例化' : '当前不可实例化'"
              placement="top"
            >
```

### Verification

List shows tag chips for seeded video templates after migration.

---

### Task FE5 — GraphTemplateDesignerView: remove type radio + stop writing `run_kind`

**File:** `frontend/src/views/GraphTemplateDesignerView.vue`  
**Estimated time:** 4 minutes

Remove from `form` reactive object:

```typescript
  runKind: 'batch' as 'batch' | 'production',
```

Remove from `applyDetail`:

```typescript
  form.runKind = (next.config?.run_kind === 'production' ? 'production' : 'batch')
```

In `buildTemplateConfig`, delete line:

```typescript
    run_kind: form.runKind,
```

Remove template block (~lines 711–717):

```html
          <el-form-item label="模板类型">
            ...
          </el-form-item>
```

Optional legacy badge (advanced):

```html
          <el-form-item v-if="detail?.config?.run_kind" label="遗留字段">
            <el-tag type="info" effect="plain">run_kind={{ detail.config.run_kind }}</el-tag>
          </el-form-item>
```

### Verification

```bash
cd frontend && npm run test:unit -- GraphTemplateDesignerView.spec.ts -x
```

Expected: `PASS` (update spec to not expect 模板类型 text).

---

### Task FE6 — GraphTemplateDesignerView: tag editor

**File:** `frontend/src/views/GraphTemplateDesignerView.vue`  
**Estimated time:** 4 minutes

Add import:

```typescript
import { updateGraphTemplateTags } from '@/api/workflow-graph'
```

Add ref:

```typescript
const tagInput = ref<string[]>([])
```

In `applyDetail`:

```typescript
  tagInput.value = [...(next.tags ?? [])]
```

Add save handler:

```typescript
async function handleSaveTags(): Promise<void> {
  if (!templateId.value) {
    return
  }
  saving.value = true
  try {
    await updateGraphTemplateTags(templateId.value, tagInput.value)
    applyDetail(await getGraphTemplateDesigner(templateId.value))
    ElMessage.success('标签已保存')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}
```

In 模板信息 form (after 说明):

```html
          <el-form-item label="标签">
            <el-select
              v-model="tagInput"
              multiple
              filterable
              allow-create
              default-first-option
              :disabled="detail?.status === 'archived'"
              placeholder="输入后回车添加"
              data-testid="designer-tags"
              style="width: 100%"
            />
            <el-button
              class="designer__tag-save"
              size="small"
              :loading="saving"
              data-testid="designer-tags-save"
              @click="handleSaveTags"
            >
              保存标签
            </el-button>
          </el-form-item>
```

### Verification

Designer → add tag → 保存标签 → reload shows persisted tags.

---

### Task FE7 — GraphTemplateDesignerView: capabilities readout + archive

**File:** `frontend/src/views/GraphTemplateDesignerView.vue`  
**Estimated time:** 4 minutes

Add import `archiveGraphTemplate`; add `archiving` ref.

Handler:

```typescript
async function handleArchive(): Promise<void> {
  if (!templateId.value || detail.value?.status !== 'active') {
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认归档「${detail.value.name}」？归档后不可原地编辑。`,
      '归档模板',
      { type: 'warning', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  archiving.value = true
  try {
    await archiveGraphTemplate(templateId.value)
    ElMessage.success('模板已归档')
    void router.push({ name: 'task-templates', query: { status: 'archived' } })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    archiving.value = false
  }
}
```

Toolbar button (before 发布):

```html
        <el-button
          v-if="detail?.status === 'active'"
          type="warning"
          plain
          :loading="archiving"
          data-testid="designer-archive"
          @click="handleArchive"
        >
          归档
        </el-button>
```

Capabilities panel in 模板信息 card:

```html
          <el-form-item v-if="detail?.capabilities" label="派生能力（只读）">
            <div data-testid="designer-capabilities">
              <el-tag
                v-for="hint in detail.capabilities.derived_hints"
                :key="hint"
                size="small"
                effect="plain"
              >
                {{ hint }}
              </el-tag>
              <span v-if="!detail.capabilities.derived_hints.length">—</span>
            </div>
          </el-form-item>
```

Extend `GraphTemplateDesignerDetail` / API mapping if capabilities not yet on designer GET (mirror list builder in B9).

### Verification

Active template designer shows 归档 button and capability hints.

---

### Task FE8 — ACTIVE edit contract: disable save-settings + rename

**File:** `frontend/src/views/GraphTemplateDesignerView.vue`  
**Estimated time:** 3 minutes

Add computed:

```typescript
const isArchived = computed(() => detail.value?.status === 'archived')
const definitionLocked = computed(() => !isDraft.value)
```

Remove/hide `designer-save-settings` button entirely.

Replace alert (~line 685):

```html
    <el-alert
      v-if="detail && definitionLocked"
      type="info"
      :closable="false"
      show-icon
      class="designer__alert"
      title="已发布模板不可原地修改定义。请使用「另存新版本」编辑图结构；标签可单独保存。"
    />
```

Disable name/description/graph fields when `definitionLocked`:

```html
            <el-input v-model="form.name" :disabled="definitionLocked" ... />
```

**File:** `frontend/src/components/workflow/GraphTemplateEditDialog.vue`

Add computed:

```typescript
const definitionLocked = computed(() => {
  const status = props.template?.status
  return status === 'active' || status === 'archived'
})
```

Disable inputs + save when locked; update footer:

```html
      <el-button
        v-if="!definitionLocked"
        type="primary"
        :loading="saving"
        data-testid="graph-template-edit-save"
        @click="handleSave"
      >
        保存
      </el-button>
      <p v-else class="graph-template-edit__meta">已发布模板请在设计器中「另存新版本」后改名。</p>
```

Hide `run_kind` from meta line; show tags if present.

### Verification

```bash
cd frontend && npm run test:unit -- GraphTemplateDesignerView.spec.ts GraphTemplateEditDialog.spec.ts -x 2>&1 | tail -6
```

---

## Frontend tests

### Task FE-T1 — GraphTemplatesPanel archive + filter tests

**File:** `frontend/tests/GraphTemplatesPanel.spec.ts` (new)  
**Estimated time:** 5 minutes

```typescript
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GraphTemplatesPanel from '@/components/workflow/GraphTemplatesPanel.vue'

const archiveGraphTemplate = vi.fn()
const listGraphTemplates = vi.fn()

vi.mock('@/api/task-center', () => ({ getTaskCenterSnapshot: vi.fn().mockResolvedValue({ publish_department_options: [] }) }))
vi.mock('@/api/profiles', () => ({ getProfile: vi.fn() }))
vi.mock('@/api/workflow-graph', () => ({
  listGraphTemplates,
  archiveGraphTemplate,
  createBlankGraphTemplate: vi.fn(),
  cloneGraphTemplate: vi.fn(),
  deleteGraphTemplate: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: null }) }))

describe('GraphTemplatesPanel', () => {
  beforeEach(() => {
    listGraphTemplates.mockResolvedValue([
      {
        id: 'tpl-active',
        code: 'demo_v1',
        name: 'Demo',
        status: 'active',
        version: 1,
        tags: ['视频'],
        capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
      },
    ])
    archiveGraphTemplate.mockResolvedValue({ id: 'tpl-active', status: 'archived', nodes: [], edges: [] })
  })

  it('loads with working status filter by default', async () => {
    mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true } },
    })
    await flushPromises()
    expect(listGraphTemplates).toHaveBeenCalledWith({
      manage: true,
      status: ['draft', 'active'],
      q: '',
    })
  })

  it('renders archive button for active templates', async () => {
    const wrapper = mount(GraphTemplatesPanel, {
      props: { canPublish: true, canManage: true },
      global: { plugins: [ElementPlus], stubs: { TemplateInstantiateDialog: true, GraphTemplateEditDialog: true } },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="graph-template-archive"]').exists()).toBe(true)
  })
})
```

### Verification

```bash
cd frontend && npm run test:unit -- GraphTemplatesPanel.spec.ts -x
```

Expected: `2 passed`

---

### Task FE-T2 — GraphTemplateDesignerView ACTIVE lock test

**File:** `frontend/tests/GraphTemplateDesignerView.spec.ts`  
**Append test:**  
**Estimated time:** 3 minutes

```typescript
  it('hides save-settings and shows immutability banner for active templates', async () => {
    const { getGraphTemplateDesigner } = await import('@/api/workflow-graph')
    vi.mocked(getGraphTemplateDesigner).mockResolvedValueOnce({
      id: 'tpl-1',
      code: 'topic_meeting_batch_v1',
      base_code: 'topic_meeting_batch_v1',
      name: '选题会（批次）',
      description: null,
      status: 'active',
      version: 1,
      run_kind: 'batch',
      tags: ['视频'],
      capabilities: { can_instantiate_directly: true, derived_hints: ['可直接发起'] },
      config: { aggregate_mode: 'batch', launch_schema: { fields: [] } },
      has_instances: false,
      structure_locked: false,
      nodes: [],
      edges: [],
    })
    const wrapper = mount(GraphTemplateDesignerView, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="designer-save-settings"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('不可原地修改定义')
  })
```

### Verification

```bash
cd frontend && npm run test:unit -- GraphTemplateDesignerView.spec.ts -x
```

Expected: all tests `PASS`

---

## Exit checklist (Phase 1)

- [ ] M-01: `archiveGraphTemplate` + list/designer archive + confirm
- [ ] M-02: status filter shows archived; default draft+active unchanged
- [ ] M-03: no type radio; tags + capabilities on list; gates use capabilities (+ legacy fallback)
- [ ] M-04: ACTIVE/ARCHIVED definition edits disabled; tags-only PATCH works
- [ ] M-05: `q` search + status filter compose
- [ ] Video v1 seeds still instantiate/fork/schedule (regression suite green)
- [ ] Update `memory-bank/knowledge/contracts/database/graph-engine-schema.md` + `data-contracts` in implementation session

# Status

**proposed**
