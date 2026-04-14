from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ReportingLineType, UserRole
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Profile, ProfileFieldDefinition, ProfileFieldPermission, User
from app.services.access_control import (
  ensure_management_role,
  get_effective_managed_department_ids,
  get_effective_reporting_line_types,
)

CORE_PROFILE_FIELDS: dict[str, str] = {
  "employee_no": "employee_no",
  "real_name": "real_name",
  "department_id": "department_id",
  "job_title": "job_title",
  "phone": "phone",
  "hire_date": "hire_date",
}

DEFAULT_FIELD_DEFINITIONS: tuple[dict[str, Any], ...] = (
  {
    "field_key": "employee_no",
    "label": "员工编号",
    "field_type": "string",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "real_name",
    "label": "姓名",
    "field_type": "string",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "department_id",
    "label": "主部门",
    "field_type": "uuid",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "job_title",
    "label": "岗位名称",
    "field_type": "string",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "phone",
    "label": "联系电话",
    "field_type": "string",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "hire_date",
    "label": "入职日期",
    "field_type": "date",
    "storage_target": "core",
    "is_sensitive": False,
  },
  {
    "field_key": "salary",
    "label": "薪资",
    "field_type": "number",
    "storage_target": "custom",
    "is_sensitive": True,
  },
  {
    "field_key": "performance",
    "label": "绩效评估",
    "field_type": "text",
    "storage_target": "custom",
    "is_sensitive": True,
  },
  {
    "field_key": "reward_notes",
    "label": "奖惩记录",
    "field_type": "text",
    "storage_target": "custom",
    "is_sensitive": True,
  },
  {
    "field_key": "promotion_notes",
    "label": "晋升记录",
    "field_type": "text",
    "storage_target": "custom",
    "is_sensitive": True,
  },
)


@dataclass(slots=True)
class ProfileAccessContext:
  actor: User
  profile: Profile
  is_self: bool
  is_department_manager: bool
  reporting_line_types: set[ReportingLineType]


@dataclass(slots=True)
class ResolvedProfileField:
  field_key: str
  label: str
  field_type: str
  storage_target: str
  is_sensitive: bool
  value: Any
  can_view: bool
  can_edit: bool


def _infer_field_type(value: Any) -> str:
  if isinstance(value, bool):
    return "boolean"
  if isinstance(value, int | float):
    return "number"
  if isinstance(value, str):
    return "string"
  if isinstance(value, date):
    return "date"
  if isinstance(value, list):
    return "array"
  if isinstance(value, dict):
    return "object"
  return "json"


def _build_default_permissions(definition: ProfileFieldDefinition) -> list[dict[str, Any]]:
  admin_hr_rules = [
    {"subject_type": "role", "subject_value": UserRole.ADMIN.value, "can_view": True, "can_edit": True},
    {"subject_type": "role", "subject_value": UserRole.HR.value, "can_view": True, "can_edit": True},
  ]

  if definition.field_key == "salary":
    return admin_hr_rules

  if definition.field_key in {"performance", "reward_notes", "promotion_notes"}:
    return [
      *admin_hr_rules,
      {
        "subject_type": "reporting_line",
        "subject_value": ReportingLineType.SOLID.value,
        "can_view": True,
        "can_edit": True,
      },
      {
        "subject_type": "reporting_line",
        "subject_value": ReportingLineType.DOTTED.value,
        "can_view": True,
        "can_edit": False,
      },
    ]

  return [
    {"subject_type": "self", "subject_value": None, "can_view": True, "can_edit": False},
    *admin_hr_rules,
    {"subject_type": "department_manager", "subject_value": None, "can_view": True, "can_edit": False},
    {
      "subject_type": "reporting_line",
      "subject_value": ReportingLineType.SOLID.value,
      "can_view": True,
      "can_edit": False,
    },
    {
      "subject_type": "reporting_line",
      "subject_value": ReportingLineType.DOTTED.value,
      "can_view": True,
      "can_edit": False,
    },
  ]


class ProfileFieldPolicyService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  async def ensure_default_definitions(self) -> None:
    existing_definitions = {
      definition.field_key: definition
      for definition in await self._load_definitions(include_inactive=True)
    }
    for payload in DEFAULT_FIELD_DEFINITIONS:
      if payload["field_key"] in existing_definitions:
        continue
      definition = ProfileFieldDefinition(
        field_key=payload["field_key"],
        label=payload["label"],
        field_type=payload["field_type"],
        storage_target=payload["storage_target"],
        is_sensitive=payload["is_sensitive"],
        config={},
      )
      self._session.add(definition)

    await self._session.flush()
    definitions = {
      definition.field_key: definition
      for definition in await self._load_definitions(include_inactive=True)
    }
    for definition in definitions.values():
      if definition.permissions:
        continue
      for permission_payload in _build_default_permissions(definition):
        self._session.add(
          ProfileFieldPermission(
            field_definition_id=definition.id,
            subject_type=permission_payload["subject_type"],
            subject_value=permission_payload["subject_value"],
            can_view=permission_payload["can_view"],
            can_edit=permission_payload["can_edit"],
            scope_filters={},
            priority=100,
          )
        )
    await self._session.flush()

  async def ensure_custom_field_definitions(self, field_values: dict[str, Any] | Iterable[str]) -> None:
    await self.ensure_default_definitions()

    if isinstance(field_values, dict):
      pending_items = field_values.items()
    else:
      pending_items = ((field_key, None) for field_key in field_values)

    existing_definitions = {
      definition.field_key: definition
      for definition in await self._load_definitions(include_inactive=True)
    }
    for field_key, value in pending_items:
      if field_key in CORE_PROFILE_FIELDS or field_key in existing_definitions:
        continue
      definition = ProfileFieldDefinition(
        field_key=field_key,
        label=field_key,
        field_type=_infer_field_type(value),
        storage_target="custom",
        is_sensitive=False,
        config={},
      )
      self._session.add(definition)

    await self._session.flush()
    definitions = {
      definition.field_key: definition
      for definition in await self._load_definitions(include_inactive=True)
    }
    for field_key, definition in definitions.items():
      if definition.permissions or definition.storage_target != "custom":
        continue
      if field_key in CORE_PROFILE_FIELDS:
        continue
      for permission_payload in _build_default_permissions(definition):
        self._session.add(
          ProfileFieldPermission(
            field_definition_id=definition.id,
            subject_type=permission_payload["subject_type"],
            subject_value=permission_payload["subject_value"],
            can_view=permission_payload["can_view"],
            can_edit=permission_payload["can_edit"],
            scope_filters={},
            priority=100,
          )
        )
    await self._session.flush()

  async def list_definitions(self, *, actor: User) -> list[ProfileFieldDefinition]:
    ensure_management_role(actor)
    await self.ensure_default_definitions()
    return await self._load_definitions()

  async def create_definition(
    self,
    *,
    actor: User,
    field_key: str,
    label: str,
    field_type: str,
    storage_target: str,
    is_sensitive: bool = False,
    config: dict[str, Any] | None = None,
    is_active: bool = True,
  ) -> ProfileFieldDefinition:
    ensure_management_role(actor)
    await self.ensure_default_definitions()
    existing = await self._session.scalar(
      select(ProfileFieldDefinition).where(ProfileFieldDefinition.field_key == field_key)
    )
    if existing is not None:
      raise ConflictError("字段标识已存在。")

    definition = ProfileFieldDefinition(
      field_key=field_key,
      label=label,
      field_type=field_type,
      storage_target=storage_target,
      is_sensitive=is_sensitive,
      config=config or {},
      is_active=is_active,
    )
    self._session.add(definition)
    await self._session.flush()
    for permission_payload in _build_default_permissions(definition):
      self._session.add(
        ProfileFieldPermission(
          field_definition_id=definition.id,
          subject_type=permission_payload["subject_type"],
          subject_value=permission_payload["subject_value"],
          can_view=permission_payload["can_view"],
          can_edit=permission_payload["can_edit"],
          scope_filters={},
          priority=100,
        )
      )
    await self._session.commit()
    await self._session.refresh(definition)
    return definition

  async def update_definition(
    self,
    *,
    actor: User,
    definition_id,
    label: str | None = None,
    field_type: str | None = None,
    storage_target: str | None = None,
    is_sensitive: bool | None = None,
    config: dict[str, Any] | None = None,
    is_active: bool | None = None,
  ) -> ProfileFieldDefinition:
    ensure_management_role(actor)
    definition = await self._session.get(ProfileFieldDefinition, definition_id)
    if definition is None:
      raise NotFoundError("字段定义不存在。")

    if label is not None:
      definition.label = label
    if field_type is not None:
      definition.field_type = field_type
    if storage_target is not None:
      definition.storage_target = storage_target
    if is_sensitive is not None:
      definition.is_sensitive = is_sensitive
    if config is not None:
      definition.config = config
    if is_active is not None:
      definition.is_active = is_active

    await self._session.commit()
    await self._session.refresh(definition)
    return definition

  async def list_permissions(
    self,
    *,
    actor: User,
    field_definition_id,
  ) -> list[ProfileFieldPermission]:
    ensure_management_role(actor)
    statement = (
      select(ProfileFieldPermission)
      .where(ProfileFieldPermission.field_definition_id == field_definition_id)
      .order_by(ProfileFieldPermission.priority.asc(), ProfileFieldPermission.created_at.asc())
    )
    return list(await self._session.scalars(statement))

  async def create_permission(
    self,
    *,
    actor: User,
    field_definition_id,
    subject_type: str,
    subject_value: str | None = None,
    can_view: bool = False,
    can_edit: bool = False,
    scope_filters: dict[str, Any] | None = None,
    priority: int = 100,
  ) -> ProfileFieldPermission:
    ensure_management_role(actor)
    definition = await self._session.get(ProfileFieldDefinition, field_definition_id)
    if definition is None:
      raise NotFoundError("字段定义不存在。")

    permission = ProfileFieldPermission(
      field_definition_id=field_definition_id,
      subject_type=subject_type,
      subject_value=subject_value,
      can_view=can_view,
      can_edit=can_edit,
      scope_filters=scope_filters or {},
      priority=priority,
    )
    self._session.add(permission)
    await self._session.commit()
    await self._session.refresh(permission)
    return permission

  async def update_permission(
    self,
    *,
    actor: User,
    permission_id,
    subject_type: str | None = None,
    subject_value: str | None = None,
    can_view: bool | None = None,
    can_edit: bool | None = None,
    scope_filters: dict[str, Any] | None = None,
    priority: int | None = None,
  ) -> ProfileFieldPermission:
    ensure_management_role(actor)
    permission = await self._session.get(ProfileFieldPermission, permission_id)
    if permission is None:
      raise NotFoundError("字段权限不存在。")

    if subject_type is not None:
      permission.subject_type = subject_type
    if subject_value is not None:
      permission.subject_value = subject_value
    if can_view is not None:
      permission.can_view = can_view
    if can_edit is not None:
      permission.can_edit = can_edit
    if scope_filters is not None:
      permission.scope_filters = scope_filters
    if priority is not None:
      permission.priority = priority

    await self._session.commit()
    await self._session.refresh(permission)
    return permission

  async def resolve_profile_fields(
    self,
    *,
    actor: User,
    profile: Profile,
    include_custom_keys: set[str] | None = None,
  ) -> list[ResolvedProfileField]:
    await self.ensure_default_definitions()
    await self.ensure_custom_field_definitions(profile.custom_fields)
    definitions = await self._load_definitions()
    context = await self._build_access_context(actor=actor, profile=profile)

    resolved_fields: list[ResolvedProfileField] = []
    for definition in definitions:
      value = self._get_field_value(profile=profile, definition=definition)
      if definition.storage_target == "custom" and definition.field_key not in profile.custom_fields and (
        include_custom_keys is None or definition.field_key not in include_custom_keys
      ):
        continue

      matching_permissions = [
        permission
        for permission in definition.permissions
        if self._permission_matches(permission=permission, context=context)
      ]
      can_view = any(permission.can_view for permission in matching_permissions)
      can_edit = any(permission.can_edit for permission in matching_permissions)
      resolved_fields.append(
        ResolvedProfileField(
          field_key=definition.field_key,
          label=definition.label,
          field_type=definition.field_type,
          storage_target=definition.storage_target,
          is_sensitive=definition.is_sensitive,
          value=value if can_view else None,
          can_view=can_view,
          can_edit=can_edit,
        )
      )
    return resolved_fields

  async def get_field_access_map(
    self,
    *,
    actor: User,
    profile: Profile,
    include_custom_keys: set[str] | None = None,
  ) -> dict[str, ResolvedProfileField]:
    resolved_fields = await self.resolve_profile_fields(
      actor=actor,
      profile=profile,
      include_custom_keys=include_custom_keys,
    )
    return {field.field_key: field for field in resolved_fields}

  async def _build_access_context(
    self,
    *,
    actor: User,
    profile: Profile,
  ) -> ProfileAccessContext:
    managed_department_ids = await get_effective_managed_department_ids(self._session, actor.id)
    reporting_line_types = await get_effective_reporting_line_types(
      self._session,
      actor_id=actor.id,
      user_id=profile.user_id,
    )
    return ProfileAccessContext(
      actor=actor,
      profile=profile,
      is_self=actor.id == profile.user_id,
      is_department_manager=profile.department_id in managed_department_ids,
      reporting_line_types=reporting_line_types,
    )

  def _permission_matches(
    self,
    *,
    permission: ProfileFieldPermission,
    context: ProfileAccessContext,
  ) -> bool:
    if permission.subject_type == "self":
      return context.is_self
    if permission.subject_type == "role":
      return context.actor.role.value == permission.subject_value
    if permission.subject_type == "department_manager":
      return context.is_department_manager
    if permission.subject_type == "reporting_line":
      if permission.subject_value is None:
        return bool(context.reporting_line_types)
      return permission.subject_value in {line_type.value for line_type in context.reporting_line_types}
    return False

  def _get_field_value(
    self,
    *,
    profile: Profile,
    definition: ProfileFieldDefinition,
  ) -> Any:
    if definition.storage_target == "core":
      attribute_name = CORE_PROFILE_FIELDS[definition.field_key]
      return getattr(profile, attribute_name)
    return profile.custom_fields.get(definition.field_key)

  async def _load_definitions(self, *, include_inactive: bool = False) -> list[ProfileFieldDefinition]:
    statement = (
      select(ProfileFieldDefinition)
      .options(selectinload(ProfileFieldDefinition.permissions))
      .order_by(ProfileFieldDefinition.is_sensitive.desc(), ProfileFieldDefinition.field_key.asc())
    )
    if not include_inactive:
      statement = statement.where(ProfileFieldDefinition.is_active.is_(True))
    return list(await self._session.scalars(statement))
