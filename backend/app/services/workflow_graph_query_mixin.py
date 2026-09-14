from __future__ import annotations

"""W12-B: query/list operations mixed into WorkflowGraphService."""

class WorkflowGraphQueryMixin:
  """Read/list helpers for WorkflowGraphService."""

  async def collect_projection_task_ids(self, *, instance_id: UUID) -> set[UUID]:
    """Task ids linked to a graph instance (ROOT + node projection tasks)."""
    instance = await self._session.get(WorkflowGraphInstance, instance_id)
    if instance is None:
      return set()

    task_ids: set[UUID] = set()
    if instance.source_id is not None:
      task_ids.add(instance.source_id)

    node_instances = list(
      await self._session.scalars(
        select(WorkflowNodeInstance).where(WorkflowNodeInstance.instance_id == instance_id)
      )
    )
    for node_instance in node_instances:
      config = node_instance.config if isinstance(node_instance.config, dict) else {}
      raw_task_id = config.get("task_id")
      if isinstance(raw_task_id, str) and raw_task_id.strip():
        try:
          task_ids.add(UUID(raw_task_id.strip()))
        except ValueError:
          continue
    return task_ids

  async def get_instance(self, *, instance_id: UUID) -> WorkflowGraphInstance:
    instance: WorkflowGraphInstance | None = await self._session.scalar(
      select(WorkflowGraphInstance).where(WorkflowGraphInstance.id == instance_id)
    )
    if instance is None:
      raise NotFoundError("工作流图实例不存在。")
    return instance

  async def list_active_templates(self) -> list[WorkflowGraphTemplate]:
    return list(
      await self._session.scalars(
        select(WorkflowGraphTemplate)
        .where(WorkflowGraphTemplate.status == WorkflowGraphTemplateStatus.ACTIVE)
        .order_by(WorkflowGraphTemplate.code.asc())
      )
    )

  async def list_child_instances(
    self,
    *,
    parent_instance_id: UUID,
    limit: int = 50,
    include_completed: bool = False,
  ) -> list[WorkflowGraphInstance]:
    await self.get_instance(instance_id=parent_instance_id)
    normalized_limit = max(1, min(limit, 100))
    query = (
      select(WorkflowGraphInstance)
      .where(WorkflowGraphInstance.parent_instance_id == parent_instance_id)
      .order_by(WorkflowGraphInstance.created_at.asc())
      .limit(normalized_limit)
    )
    if not include_completed:
      query = query.where(WorkflowGraphInstance.status != WorkflowGraphInstanceStatus.COMPLETED)
    return list(await self._session.scalars(query))

  async def list_instances_for_template(
    self,
    *,
    template_id: UUID,
    limit: int = 10,
  ) -> list[WorkflowGraphInstance]:
    template_exists = await self._session.scalar(
      select(WorkflowGraphTemplate.id).where(WorkflowGraphTemplate.id == template_id)
    )
    if template_exists is None:
      raise NotFoundError("工作流图模板不存在。")

    normalized_limit = max(1, min(limit, 50))
    return list(
      await self._session.scalars(
        select(WorkflowGraphInstance)
        .where(WorkflowGraphInstance.template_id == template_id)
        .order_by(WorkflowGraphInstance.created_at.desc())
        .limit(normalized_limit)
      )
    )

  async def list_node_instances_for_graph(
    self,
    *,
    instance_id: UUID,
  ) -> list[WorkflowNodeInstance]:
    return list(
      await self._session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.instance_id == instance_id)
        .order_by(WorkflowNodeInstance.created_at.asc())
      )
    )

  async def list_department_runs(
    self,
    *,
    department_id: UUID,
    limit: int = 50,
    include_completed: bool = True,
  ) -> list[DepartmentRunSummary]:
    normalized_limit = max(1, min(limit, 100))
    query = (
      select(WorkflowGraphInstance)
      .where(
        WorkflowGraphInstance.department_id == department_id,
        WorkflowGraphInstance.parent_instance_id.is_(None),
      )
      .order_by(WorkflowGraphInstance.created_at.desc())
      .limit(normalized_limit)
    )
    if not include_completed:
      query = query.where(WorkflowGraphInstance.status != WorkflowGraphInstanceStatus.COMPLETED)
    instances = list(await self._session.scalars(query))
    if not instances:
      return []

    instance_ids = [instance.id for instance in instances]
    counts_raw = await self._session.execute(
      select(WorkflowRunEvent.instance_id, func.count())
      .where(WorkflowRunEvent.instance_id.in_(instance_ids))
      .group_by(WorkflowRunEvent.instance_id)
    )
    event_counts = {row[0]: int(row[1]) for row in counts_raw}

    summaries: list[DepartmentRunSummary] = []
    for instance in instances:
      run_label = instance.run_label
      if (not run_label or not str(run_label).strip()) and isinstance(instance.context, dict):
        raw = instance.context.get("run_label")
        if raw is not None:
          run_label = str(raw)
      summaries.append(
        DepartmentRunSummary(
          instance_id=instance.id,
          run_label=str(run_label).strip() if run_label else None,
          status=instance.status,
          created_at=instance.created_at,
          event_count=event_counts.get(instance.id, 0),
          department_id=instance.department_id,
        )
      )
    return summaries
