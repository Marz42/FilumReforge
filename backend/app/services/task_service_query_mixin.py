from __future__ import annotations

"""W12-A: query/read-model operations mixed into TaskService."""

class TaskServiceQueryMixin:
  """Read-model and list/query methods for TaskService."""

  async def list_tasks(self, *, actor: User) -> list[Task]:
    ensure_active_user(actor)

    statement = await self._build_visible_task_statement(actor=actor)
    result = await self._session.scalars(statement)
    return list(result)

  async def list_tasks_by_ids(self, *, actor: User, task_ids: list[UUID]) -> list[Task]:
    ensure_active_user(actor)
    if not task_ids:
      return []
    if len(task_ids) > MAX_BATCH_TASK_IDS:
      raise ConflictError(f"单次最多查询 {MAX_BATCH_TASK_IDS} 个任务。")

    unique_task_ids = list(dict.fromkeys(task_ids))
    statement = (await self._build_visible_task_statement(actor=actor)).where(
      Task.id.in_(unique_task_ids)
    )
    tasks = list(await self._session.scalars(statement))
    task_map = {task.id: task for task in tasks}
    return [task_map[task_id] for task_id in unique_task_ids if task_id in task_map]

  async def search_tasks(self, *, actor: User, query: str, limit: int = 30) -> list[Task]:
    ensure_active_user(actor)
    normalized = query.strip()
    if not normalized:
      return []

    pattern = f"%{normalized}%"
    statement = (
      (await self._build_visible_task_statement(actor=actor))
      .where(
        or_(
          Task.title.ilike(pattern),
          Task.description.ilike(pattern),
        )
      )
      .order_by(Task.updated_at.desc())
      .limit(max(1, min(limit, 100)))
    )
    return list(await self._session.scalars(statement))

  async def get_task(self, *, actor: User, task_id: UUID) -> Task:
    ensure_active_user(actor)

    statement = (await self._build_visible_task_statement(actor=actor)).where(Task.id == task_id)
    task = await self._session.scalar(statement)
    if task is None:
      raise NotFoundError("任务不存在。")
    return task

  async def list_task_inbox(
    self,
    *,
    actor: User,
    limit: int = 10,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskInboxEntry]:
    ensure_active_user(actor)

    pending_workflow_task_ids = list(
      await self._session.scalars(
        select(WorkflowInstance.source_id)
        .join(WorkflowInstance.step_runs)
        .where(
          WorkflowInstance.source_type == "task",
          WorkflowInstance.source_id.is_not(None),
          WorkflowStepRun.assignee_user_id == actor.id,
          WorkflowStepRun.status == WorkflowStepRunStatus.PENDING,
        )
      )
    )
    candidate_task_ids = {
      task_id
      for task_id in pending_workflow_task_ids
      if task_id is not None
    }
    # Always include tasks where this actor is the standalone action owner.
    # ADMIN/HR visibility scans are org-wide and ordered by created_at; a task
    # created earlier then delegated to them can fall outside the scan window
    # and silently disappear from「待处理」while still showing in「任务跟踪」.
    action_owner_task_ids = {
      task_id
      for task_id in await self._session.scalars(
        select(Task.id).where(
          or_(
            and_(
              Task.assignee_id == actor.id,
              Task.status.in_((TaskStatus.TODO, TaskStatus.DOING, TaskStatus.BLOCKED)),
            ),
            and_(
              Task.creator_id == actor.id,
              Task.status == TaskStatus.REVIEW,
            ),
          )
        )
      )
    }
    tasks = list(
      await self._session.scalars(
        (await self._build_visible_task_statement(actor=actor)).limit(
          self._list_scan_limit(limit=limit)
        )
      )
    )
    scanned_ids = {task.id for task in tasks}
    missing_owner_ids = (candidate_task_ids | action_owner_task_ids) - scanned_ids
    if missing_owner_ids:
      extra_tasks = list(
        await self._session.scalars(
          select(Task)
          .options(
            selectinload(Task.creator).selectinload(User.profile),
            selectinload(Task.assignee).selectinload(User.profile),
            selectinload(Task.department),
            selectinload(Task.watchers),
          )
          .where(Task.id.in_(missing_owner_ids))
        )
      )
      tasks = [*tasks, *extra_tasks]
    graph_projection_map, graph_projection_gaps = (
      await self._graph_task_projection_state(tasks=tasks)
      if self._task_center_v2_enabled()
      else ({}, {})
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)
    step_context_map = await self._task_step_context_map(
      task_ids=[task.id for task in tasks if task.id not in graph_projection_map]
    )

    graph_entries: list[tuple[Task, TaskInboxEntry]] = []
    legacy_tasks: list[Task] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      if self._is_graph_run_root_shell_task(task):
        continue
      if self._strict_projection_missing(
        task=task,
        graph_projection_map=graph_projection_map,
      ):
        self._record_strict_projection_gap(
          surface="inbox",
          task=task,
          gap=graph_projection_gaps.get(task.id),
        )
        continue
      projection = graph_projection_map.get(task.id)
      if projection is not None:
        action_context = self._work_item_action_context(
          task=task,
          actor=actor,
          projection=projection,
        )
        if projection.status != TaskStatus.DONE and action_context.current_action_owner_id == actor.id:
          graph_entries.append(
            (
              task,
              self._build_graph_inbox_entry(
                task=task,
                projection=projection,
                graph_run_labels=graph_run_labels,
                actor=actor,
              ),
            )
          )
        continue
      if task.status == TaskStatus.DONE:
        continue
      if task.id in candidate_task_ids:
        legacy_tasks.append(task)
        continue
      if self._uses_graph_handshake_cycle(task=task) and self._manual_graph_current_handler_id(task=task) == actor.id:
        legacy_tasks.append(task)
        continue
      # Standalone Work Item: the inbox owner is whoever must act next
      # (assignee while TODO/DOING, creator while REVIEW), not merely the assignee.
      if is_standalone(task):
        if standalone_action_owner_id(task) == actor.id:
          legacy_tasks.append(task)
        continue
      # Legacy fallback for non-standalone tasks without a graph projection.
      if task.assignee_id == actor.id:
        legacy_tasks.append(task)

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_graph_entries = sorted(
      graph_entries,
      key=lambda item: (
        item[0].due_date is None,
        _normalize_datetime(item[0].due_date) if item[0].due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(item[0].priority),
        -int(item[0].created_at.timestamp()),
        item[0].id,
      ),
    )
    sorted_legacy_tasks = sorted(
      legacy_tasks,
      key=lambda task: (
        task.due_date is None,
        _normalize_datetime(task.due_date) if task.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(task.priority),
        -int(task.created_at.timestamp()),
        task.id,
      ),
    )
    entries = [entry for _, entry in sorted_graph_entries]
    entries.extend(
      self._build_inbox_entry(
        task=task,
        step_context_map=step_context_map,
        graph_run_labels=graph_run_labels,
        actor=actor,
      )
      for task in sorted_legacy_tasks
    )
    return _paginate_task_center_list(
      entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

  async def list_task_tracking(
    self,
    *,
    actor: User,
    limit: int = 10,
    exclude_inbox_task_ids: set[UUID] | None = None,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskTrackingEntry]:
    ensure_active_user(actor)
    is_management = actor.role in MANAGEMENT_ROLES

    workflow_related_task_ids = {
      task_id
      for task_id in list(
        await self._session.scalars(
          select(WorkflowInstance.source_id)
          .outerjoin(WorkflowInstance.step_runs)
          .where(
            WorkflowInstance.source_type == "task",
            WorkflowInstance.source_id.is_not(None),
            or_(
              WorkflowInstance.initiator_user_id == actor.id,
              WorkflowStepRun.assignee_user_id == actor.id,
            ),
          )
        )
      )
      if task_id is not None
    }

    if is_management:
      tasks = list(
        await self._session.scalars(
          (await self._build_visible_task_statement(actor=actor))
          .where(Task.status != TaskStatus.DONE)
          .order_by(Task.updated_at.desc())
          .limit(self._list_scan_limit(limit=limit))
        )
      )
    else:
      tracking_filters = [
        Task.creator_id == actor.id,
        Task.assignee_id == actor.id,
        Task.watchers.any(TaskWatcher.user_id == actor.id),
      ]
      managed_department_ids = await get_managed_department_ids(self._session, actor.id)
      if managed_department_ids:
        tracking_filters.append(Task.department_id.in_(managed_department_ids))
      if workflow_related_task_ids:
        tracking_filters.append(Task.id.in_(workflow_related_task_ids))

      tasks = list(
        await self._session.scalars(
          select(Task)
          .options(
            selectinload(Task.creator).selectinload(User.profile),
            selectinload(Task.assignee).selectinload(User.profile),
            selectinload(Task.department),
            selectinload(Task.watchers),
          )
          .where(or_(*tracking_filters))
          .order_by(Task.updated_at.desc())
          .limit(self._list_scan_limit(limit=limit))
        )
      )

    # inbox ∩ tracking = ∅ for every role, including ADMIN/HR oversight.
    # Management still sees unrelated open tasks as「督办」, but personal
    # actionable items belong only in「待处理」.
    if exclude_inbox_task_ids is None:
      inbox_page = await self.list_task_inbox(actor=actor, limit=limit)
      inbox_task_ids = {entry.task_id for entry in inbox_page.items}
    else:
      inbox_task_ids = set(exclude_inbox_task_ids)

    graph_projection_map, graph_projection_gaps = (
      await self._graph_task_projection_state(tasks=tasks)
      if self._task_center_v2_enabled()
      else ({}, {})
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)
    step_context_map = await self._task_step_context_map(
      task_ids=[task.id for task in tasks if task.id not in graph_projection_map]
    )
    tracking_entries: list[TaskTrackingEntry] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      if task.id in inbox_task_ids:
        continue
      if not is_management and self._is_hidden_graph_root_for_non_management(task):
        continue
      if self._strict_projection_missing(
        task=task,
        graph_projection_map=graph_projection_map,
      ):
        self._record_strict_projection_gap(
          surface="tracking",
          task=task,
          gap=graph_projection_gaps.get(task.id),
        )
        continue
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids or task.id in graph_projection_map:
        relation_types.append("流程")
      is_personally_related = (
        task.creator_id == actor.id
        or task.assignee_id == actor.id
        or any(watcher.user_id == actor.id for watcher in task.watchers)
      )
      has_workflow_participation = task.id in workflow_related_task_ids or task.id in graph_projection_map
      # Iteration 3 fix: a standalone Task legitimately has no workflow participation.
      # Personally-related tasks (creator / assignee / watcher) must not be dropped
      # just because they carry no graph projection.
      if (
        self._task_center_v2_enabled()
        and not has_workflow_participation
        and not is_personally_related
        and not is_management
      ):
        continue
      if is_management and not is_personally_related:
        relation_types.append("督办")

      projection = graph_projection_map.get(task.id)
      if projection is not None:
        if projection.status == TaskStatus.DONE:
          continue
        tracking_entries.append(
          self._build_graph_tracking_entry(
            task=task,
            relation_types=relation_types or ["流程"],
            projection=projection,
            graph_run_labels=graph_run_labels,
            actor=actor,
          )
        )
      elif task.status != TaskStatus.DONE:
        tracking_entries.append(
          self._build_tracking_entry(
            task=task,
            relation_types=relation_types or ["流程"],
            step_context_map=step_context_map,
            graph_run_labels=graph_run_labels,
            actor=actor,
          )
        )

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_entries = sorted(
      tracking_entries,
      key=lambda item: (
        item.status == TaskStatus.DONE,
        item.due_date is None,
        _normalize_datetime(item.due_date) if item.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _task_priority_sort_value(item.priority),
        item.task_id,
      ),
    )
    return _paginate_task_center_list(
      sorted_entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

  async def list_task_history(
    self,
    *,
    actor: User,
    limit: int = 20,
    after_task_id: UUID | None = None,
  ) -> TaskCenterListPage[TaskHistoryEntry]:
    ensure_active_user(actor)

    workflow_related_task_ids = {
      task_id
      for task_id in list(
        await self._session.scalars(
          select(WorkflowInstance.source_id)
          .outerjoin(WorkflowInstance.step_runs)
          .where(
            WorkflowInstance.source_type == "task",
            WorkflowInstance.source_id.is_not(None),
            or_(
              WorkflowInstance.initiator_user_id == actor.id,
              WorkflowStepRun.assignee_user_id == actor.id,
            ),
          )
        )
      )
      if task_id is not None
    }
    history_filters = [
      Task.creator_id == actor.id,
      Task.assignee_id == actor.id,
      Task.watchers.any(TaskWatcher.user_id == actor.id),
    ]
    if workflow_related_task_ids:
      history_filters.append(Task.id.in_(workflow_related_task_ids))

    tasks = list(
      await self._session.scalars(
        select(Task)
        .options(
          selectinload(Task.creator).selectinload(User.profile),
          selectinload(Task.assignee).selectinload(User.profile),
          selectinload(Task.department),
          selectinload(Task.watchers),
        )
        .where(or_(*history_filters))
        .order_by(Task.completed_at.desc(), Task.updated_at.desc())
      )
    )

    graph_projection_map, graph_projection_gaps = (
      await self._graph_task_projection_state(tasks=tasks)
      if self._task_center_v2_enabled()
      else ({}, {})
    )
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=tasks)

    entries: list[TaskHistoryEntry] = []
    for task in tasks:
      if self._is_admin_archived_task(task):
        continue
      if self._strict_projection_missing(
        task=task,
        graph_projection_map=graph_projection_map,
      ):
        self._record_strict_projection_gap(
          surface="history",
          task=task,
          gap=graph_projection_gaps.get(task.id),
        )
        continue
      relation_types: list[str] = []
      if task.creator_id == actor.id:
        relation_types.append("发起")
      if task.assignee_id == actor.id:
        relation_types.append("执行")
      if any(watcher.user_id == actor.id for watcher in task.watchers):
        relation_types.append("关注")
      if task.id in workflow_related_task_ids or task.id in graph_projection_map:
        relation_types.append("流程")
      projection = graph_projection_map.get(task.id)
      if projection is not None:
        if projection.status != TaskStatus.DONE:
          continue
        entries.append(
          self._build_graph_history_entry(
            task=task,
            relation_types=relation_types or ["相关"],
            projection=projection,
            graph_run_labels=graph_run_labels,
          )
        )
      elif task.status == TaskStatus.DONE:
        entries.append(
          self._build_history_entry(
            task=task,
            relation_types=relation_types or ["相关"],
            graph_run_labels=graph_run_labels,
            status=task.status,
          )
        )

    # task id as final tiebreaker: cursor pagination requires a fully deterministic order.
    sorted_entries = sorted(
      entries,
      key=lambda item: (
        item.completed_at is None,
        _normalize_datetime(item.completed_at) if item.completed_at is not None else datetime.max.replace(tzinfo=UTC),
        item.task_id,
      ),
      reverse=True,
    )
    return _paginate_task_center_list(
      sorted_entries,
      limit=limit,
      after_task_id=after_task_id,
      task_id_getter=lambda entry: entry.task_id,
    )

  async def list_task_comments(self, *, actor: User, task_id: UUID) -> list[TaskComment]:
    await self.get_task(actor=actor, task_id=task_id)

    statement = (
      select(TaskComment)
      .options(selectinload(TaskComment.user).selectinload(User.profile))
      .where(TaskComment.task_id == task_id)
      .order_by(TaskComment.created_at.asc())
    )
    if actor.role not in MANAGEMENT_ROLES:
      statement = statement.where(TaskComment.is_internal.is_(False))

    result = await self._session.scalars(statement)
    return list(result)

  async def list_task_logs(self, *, actor: User, task_id: UUID) -> list[TaskLog]:
    await self.get_task(actor=actor, task_id=task_id)

    result = await self._session.scalars(
      select(TaskLog)
      .where(TaskLog.task_id == task_id)
      .order_by(TaskLog.created_at.asc())
    )
    return list(result)

  async def list_task_activity(self, *, actor: User, task_id: UUID) -> list[TaskActivityEntry]:
    comments = await self.list_task_comments(actor=actor, task_id=task_id)
    logs = await self.list_task_logs(actor=actor, task_id=task_id)

    activity = [
      *(
        TaskActivityEntry(entry_type="comment", created_at=comment.created_at, comment=comment)
        for comment in comments
      ),
      *(
        TaskActivityEntry(entry_type="log", created_at=log.created_at, log=log)
        for log in logs
      ),
    ]
    activity.sort(key=lambda entry: (_normalize_datetime(entry.created_at), entry.entry_type))
    return activity

  async def list_task_watchers(self, *, actor: User, task_id: UUID) -> list[TaskWatcher]:
    task = await self.get_task(actor=actor, task_id=task_id)
    if not await self._can_operate_task(actor=actor, task=task):
      raise AuthorizationError("当前账号不能查看该任务关注人。")

    result = await self._session.scalars(
      select(TaskWatcher)
      .options(selectinload(TaskWatcher.user), selectinload(TaskWatcher.creator))
      .where(TaskWatcher.task_id == task_id)
      .order_by(TaskWatcher.created_at.asc())
    )
    return list(result)

  async def list_overdue_tasks(self) -> list[Task]:
    result = await self._session.scalars(
      select(Task)
      .options(
        selectinload(Task.assignee),
        selectinload(Task.department).selectinload(Department.manager),
      )
      .where(
        Task.due_date.is_not(None),
        Task.due_date < datetime.now(UTC),
        Task.status != TaskStatus.DONE,
      )
      .order_by(Task.due_date.asc())
    )
    return list(result)

  async def get_task_stats_summary(
    self,
    *,
    actor: User,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
  ) -> TaskStatsSummary:
    now = datetime.now(UTC)
    resolved_start, resolved_end, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    created_condition = and_(Task.created_at >= start_at, Task.created_at < end_at)
    completed_condition = and_(Task.completed_at >= start_at, Task.completed_at < end_at)
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_cutoff = min(now, end_at)
    matured_due_condition = and_(due_condition, Task.due_date < matured_cutoff)
    on_time_condition = and_(
      matured_due_condition,
      Task.completed_at.is_not(None),
      Task.completed_at <= Task.due_date,
    )
    period_overdue_condition = and_(
      matured_due_condition,
      or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
    )
    current_overdue_condition = and_(
      Task.due_date.is_not(None),
      Task.due_date < now,
      Task.status != TaskStatus.DONE,
    )
    aggregate = select(
      func.count(Task.id),
      func.count(Task.id).filter(Task.status == TaskStatus.DONE),
      func.count(Task.id).filter(current_overdue_condition),
      func.count(Task.id).filter(created_condition),
      func.count(Task.id).filter(completed_condition),
      func.count(Task.id).filter(due_condition),
      func.count(Task.id).filter(matured_due_condition),
      func.count(Task.id).filter(on_time_condition),
      func.count(Task.id).filter(period_overdue_condition),
      func.count(Task.id).filter(Task.status != TaskStatus.DONE),
      *[
        func.count(Task.id).filter(Task.status == status).label(f"status_{status.value}")
        for status in TaskStatus
      ],
    ).where(*filters)
    row = (await self._session.execute(aggregate)).one()
    (
      total_tasks,
      completed_tasks,
      overdue_tasks,
      created_tasks,
      period_completed_tasks,
      due_tasks,
      matured_due_tasks,
      on_time_completed_tasks,
      period_overdue_tasks,
      current_open_tasks,
      *status_counts,
    ) = [int(value or 0) for value in row]
    tasks_by_status = dict(zip(TaskStatus, status_counts, strict=True))
    completion_rate = round(completed_tasks / total_tasks, 4) if total_tasks else 0.0
    overdue_rate = round(overdue_tasks / total_tasks, 4) if total_tasks else 0.0
    on_time_completion_rate = (
      round(on_time_completed_tasks / matured_due_tasks, 4)
      if matured_due_tasks
      else 0.0
    )
    return TaskStatsSummary(
      total_tasks=total_tasks,
      completed_tasks=completed_tasks,
      completion_rate=completion_rate,
      overdue_tasks=overdue_tasks,
      overdue_rate=overdue_rate,
      tasks_by_status=tasks_by_status,
      start_date=resolved_start,
      end_date=resolved_end,
      created_tasks=created_tasks,
      period_completed_tasks=period_completed_tasks,
      due_tasks=due_tasks,
      matured_due_tasks=matured_due_tasks,
      on_time_completed_tasks=on_time_completed_tasks,
      on_time_completion_rate=on_time_completion_rate,
      current_open_tasks=current_open_tasks,
      period_overdue_tasks=period_overdue_tasks,
    )

  async def get_task_workload(
    self,
    *,
    actor: User,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
  ) -> list[TaskWorkloadEntry]:
    now = datetime.now(UTC)
    _, _, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    created_condition = and_(Task.created_at >= start_at, Task.created_at < end_at)
    completed_condition = and_(Task.completed_at >= start_at, Task.completed_at < end_at)
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_due_condition = and_(due_condition, Task.due_date < min(now, end_at))
    on_time_condition = and_(
      matured_due_condition,
      Task.completed_at.is_not(None),
      Task.completed_at <= Task.due_date,
    )
    period_overdue_condition = and_(
      matured_due_condition,
      or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
    )
    current_overdue_condition = and_(
      Task.due_date.is_not(None),
      Task.due_date < now,
      Task.status != TaskStatus.DONE,
    )
    assignee_label = func.coalesce(Profile.real_name, User.email)
    rows = (
      await self._session.execute(
        select(
          User.id,
          User.email,
          assignee_label,
          Profile.department_id,
          Department.name,
          func.count(Task.id),
          func.count(Task.id).filter(Task.status != TaskStatus.DONE),
          func.count(Task.id).filter(Task.status == TaskStatus.DONE),
          func.count(Task.id).filter(current_overdue_condition),
          func.count(Task.id).filter(created_condition),
          func.count(Task.id).filter(completed_condition),
          func.count(Task.id).filter(due_condition),
          func.count(Task.id).filter(matured_due_condition),
          func.count(Task.id).filter(on_time_condition),
          func.count(Task.id).filter(period_overdue_condition),
        )
        .join(User, User.id == Task.assignee_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(Department, Department.id == Profile.department_id)
        .where(*filters)
        .group_by(User.id, User.email, Profile.real_name, Profile.department_id, Department.name)
        .order_by(Department.name.asc().nulls_first(), assignee_label.asc())
      )
    ).all()
    result: list[TaskWorkloadEntry] = []
    for row in rows:
      matured_due_tasks = int(row[12] or 0)
      on_time_completed_tasks = int(row[13] or 0)
      result.append(
        TaskWorkloadEntry(
          assignee_id=row[0],
          assignee_email=row[1],
          assignee_label=row[2],
          department_id=row[3],
          department_name=row[4],
          total_tasks=int(row[5] or 0),
          open_tasks=int(row[6] or 0),
          completed_tasks=int(row[7] or 0),
          overdue_tasks=int(row[8] or 0),
          created_tasks=int(row[9] or 0),
          period_completed_tasks=int(row[10] or 0),
          due_tasks=int(row[11] or 0),
          matured_due_tasks=matured_due_tasks,
          on_time_completed_tasks=on_time_completed_tasks,
          on_time_completion_rate=(
            round(on_time_completed_tasks / matured_due_tasks, 4)
            if matured_due_tasks
            else 0.0
          ),
          period_overdue_tasks=int(row[14] or 0),
        )
      )
    return result

  async def list_task_stats_scopes(self, *, actor: User) -> TaskStatsScopes:
    ensure_active_user(actor)
    if is_management_role(actor):
      departments = list(
        await self._session.scalars(
          select(Department)
          .where(Department.is_active.is_(True))
          .order_by(Department.sort_order.asc(), Department.name.asc())
        )
      )
      return TaskStatsScopes(
        mode="organization",
        departments=[TaskStatsScopeOption(id=item.id, label=item.name) for item in departments],
      )

    department_ids = await get_effective_managed_department_ids(self._session, actor.id)
    if not department_ids:
      return TaskStatsScopes(mode="personal", departments=[])
    departments = list(
      await self._session.scalars(
        select(Department)
        .where(Department.id.in_(department_ids), Department.is_active.is_(True))
        .order_by(Department.sort_order.asc(), Department.name.asc())
      )
    )
    return TaskStatsScopes(
      mode="organization",
      departments=[TaskStatsScopeOption(id=item.id, label=item.name) for item in departments],
    )

  async def list_task_stats_details(
    self,
    *,
    actor: User,
    metric: str,
    department_id: UUID | None = None,
    include_subtree: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    assignee_id: UUID | None = None,
    cursor: UUID | None = None,
    limit: int = 50,
  ) -> TaskStatsDetailsPage:
    now = datetime.now(UTC)
    _, _, start_at, end_at = _resolve_task_stats_period(
      start_date=start_date,
      end_date=end_date,
      now=now,
    )
    filters = await self._build_task_stats_filters(
      actor=actor,
      department_id=department_id,
      include_subtree=include_subtree,
    )
    due_condition = and_(Task.due_date >= start_at, Task.due_date < end_at)
    matured_due_condition = and_(due_condition, Task.due_date < min(now, end_at))
    metric_conditions = {
      "created": and_(Task.created_at >= start_at, Task.created_at < end_at),
      "completed": and_(Task.completed_at >= start_at, Task.completed_at < end_at),
      "due": due_condition,
      "overdue": and_(
        matured_due_condition,
        or_(Task.completed_at.is_(None), Task.completed_at > Task.due_date),
      ),
      "on_time": and_(
        matured_due_condition,
        Task.completed_at.is_not(None),
        Task.completed_at <= Task.due_date,
      ),
      "open": Task.status != TaskStatus.DONE,
    }
    metric_condition = metric_conditions.get(metric)
    if metric_condition is None:
      raise ConflictError("不支持的统计明细指标。")
    statement = select(Task).where(*filters, metric_condition)
    if assignee_id is not None:
      statement = statement.where(Task.assignee_id == assignee_id)
    if cursor is not None:
      statement = statement.where(Task.id > cursor)
    tasks = list(
      await self._session.scalars(
        statement
        .options(
          selectinload(Task.assignee).selectinload(User.profile),
          selectinload(Task.department),
        )
        .order_by(Task.id.asc())
        .limit(limit + 1)
      )
    )
    has_more = len(tasks) > limit
    page_tasks = tasks[:limit]
    graph_run_labels = await self._load_graph_run_label_by_task_id(tasks=page_tasks)
    items = [
      TaskStatsDetailEntry(
        task_id=task.id,
        title=task.title,
        assignee_id=task.assignee_id,
        assignee_label=_user_display_label(task.assignee) or task.assignee.email,
        department_id=task.department_id,
        department_name=task.department.name if task.department is not None else None,
        source_type=task.source_type,
        run_label=resolve_task_run_label(
          title=task.title,
          metadata=self._copy_task_metadata(task),
          graph_run_label=graph_run_labels.get(task.id),
        ),
        due_date=task.due_date,
        completed_at=task.completed_at,
        is_overdue=bool(
          task.due_date is not None
          and _normalize_datetime(task.due_date) < now
          and (
            task.completed_at is None
            or _normalize_datetime(task.completed_at) > _normalize_datetime(task.due_date)
          )
        ),
      )
      for task in page_tasks
    ]
    return TaskStatsDetailsPage(
      items=items,
      next_cursor=page_tasks[-1].id if has_more and page_tasks else None,
      has_more=has_more,
    )

  async def _build_task_stats_filters(
    self,
    *,
    actor: User,
    department_id: UUID | None,
    include_subtree: bool,
  ):
    ensure_active_user(actor)
    filters: list[Any] = [
      Task.extra_metadata["admin_archived"].as_boolean().is_not(True),
      Task.extra_metadata["workflow_graph_root_task"].as_boolean().is_not(True),
    ]
    if is_management_role(actor):
      if department_id is None:
        return filters
      department_ids = (
        await expand_department_ids(self._session, {department_id})
        if include_subtree
        else {department_id}
      )
      return [*filters, Task.department_id.in_(department_ids)]

    managed_department_ids = await get_effective_managed_department_ids(self._session, actor.id)
    if not managed_department_ids:
      if department_id is not None:
        raise AuthorizationError("普通员工仅可查看本人任务统计。")
      return [*filters, Task.assignee_id == actor.id]

    if department_id is None:
      return [*filters, Task.department_id.in_(managed_department_ids)]
    if department_id not in managed_department_ids:
      raise AuthorizationError("无权查看该部门统计。")
    selected_ids = (
      (await expand_department_ids(self._session, {department_id})) & managed_department_ids
      if include_subtree
      else {department_id}
    )
    return [*filters, Task.department_id.in_(selected_ids)]

  async def get_task_board(self, *, actor: User) -> list[TaskBoardColumn]:
    tasks = await self.list_tasks(actor=actor)
    grouped: dict[TaskStatus, list[Task]] = {status: [] for status in TaskStatus}
    for task in tasks:
      grouped[task.status].append(task)
    return [TaskBoardColumn(status=status, tasks=grouped[status]) for status in TaskStatus]

  async def get_task_gantt(self, *, actor: User) -> list[TaskGanttEntry]:
    tasks = await self.list_tasks(actor=actor)
    task_ids = [task.id for task in tasks]
    dependency_rows = list(
      await self._session.scalars(
        select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
      )
    ) if task_ids else []
    dependency_map: dict[UUID, list[UUID]] = {task.id: [] for task in tasks}
    for dependency in dependency_rows:
      dependency_map.setdefault(dependency.task_id, []).append(dependency.depends_on_task_id)

    sorted_tasks = sorted(
      tasks,
      key=lambda task: (
        _normalize_datetime(task.due_date) if task.due_date is not None else datetime.max.replace(tzinfo=UTC),
        _normalize_datetime(task.created_at),
      ),
    )
    return [
      TaskGanttEntry(task=task, dependency_ids=dependency_map.get(task.id, []))
      for task in sorted_tasks
    ]
