from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
  get_current_user,
  get_delegation_service,
  get_management_user,
  get_organization_relation_service,
  get_profile_field_policy_service,
)
from app.models import User
from app.schemas.profiles import (
  DelegationCreateRequest,
  DelegationRead,
  DelegationUpdateRequest,
  PositionCreateRequest,
  PositionRead,
  ProfileFieldDefinitionCreateRequest,
  ProfileFieldDefinitionRead,
  ProfileFieldDefinitionUpdateRequest,
  ProfileFieldPermissionCreateRequest,
  ProfileFieldPermissionRead,
  ProfileFieldPermissionUpdateRequest,
)
from app.services.delegation_service import DelegationService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_field_policy_service import ProfileFieldPolicyService

router = APIRouter()


@router.get("/positions", response_model=list[PositionRead])
async def list_positions(
  _actor: Annotated[User, Depends(get_current_user)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> list[PositionRead]:
  positions = await organization_relation_service.list_positions()
  return [PositionRead.model_validate(position) for position in positions]


@router.post("/positions", response_model=PositionRead, status_code=status.HTTP_201_CREATED)
async def create_position(
  payload: PositionCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> PositionRead:
  position = await organization_relation_service.create_position(
    actor=actor,
    code=payload.code,
    name=payload.name,
    level=payload.level,
    extra_metadata=payload.extra_metadata,
    is_active=payload.is_active,
  )
  return PositionRead.model_validate(position)


@router.post("/delegations", response_model=DelegationRead, status_code=status.HTTP_201_CREATED)
async def create_delegation(
  payload: DelegationCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  delegation_service: Annotated[DelegationService, Depends(get_delegation_service)],
) -> DelegationRead:
  delegation = await delegation_service.create_delegation(
    actor=actor,
    delegator_user_id=payload.delegator_user_id,
    delegate_user_id=payload.delegate_user_id,
    scope_type=payload.scope_type,
    scope_department_id=payload.scope_department_id,
    scope_filters=payload.scope_filters,
    starts_at=payload.starts_at,
    ends_at=payload.ends_at,
  )
  return DelegationRead.model_validate(delegation)


@router.patch("/delegations/{delegation_id}", response_model=DelegationRead)
async def update_delegation(
  delegation_id: UUID,
  payload: DelegationUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  delegation_service: Annotated[DelegationService, Depends(get_delegation_service)],
) -> DelegationRead:
  delegation = await delegation_service.update_delegation(
    actor=actor,
    delegation_id=delegation_id,
    status=payload.status,
    starts_at=payload.starts_at,
    ends_at=payload.ends_at,
    scope_department_id=payload.scope_department_id,
    scope_filters=payload.scope_filters,
  )
  return DelegationRead.model_validate(delegation)


@router.get("/profile-field-definitions", response_model=list[ProfileFieldDefinitionRead])
async def list_profile_field_definitions(
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> list[ProfileFieldDefinitionRead]:
  definitions = await profile_field_policy_service.list_definitions(actor=actor)
  return [ProfileFieldDefinitionRead.model_validate(definition) for definition in definitions]


@router.post(
  "/profile-field-definitions",
  response_model=ProfileFieldDefinitionRead,
  status_code=status.HTTP_201_CREATED,
)
async def create_profile_field_definition(
  payload: ProfileFieldDefinitionCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> ProfileFieldDefinitionRead:
  definition = await profile_field_policy_service.create_definition(
    actor=actor,
    field_key=payload.field_key,
    label=payload.label,
    field_type=payload.field_type,
    storage_target=payload.storage_target,
    is_sensitive=payload.is_sensitive,
    config=payload.config,
    is_active=payload.is_active,
  )
  return ProfileFieldDefinitionRead.model_validate(definition)


@router.patch("/profile-field-definitions/{definition_id}", response_model=ProfileFieldDefinitionRead)
async def update_profile_field_definition(
  definition_id: UUID,
  payload: ProfileFieldDefinitionUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> ProfileFieldDefinitionRead:
  definition = await profile_field_policy_service.update_definition(
    actor=actor,
    definition_id=definition_id,
    label=payload.label,
    field_type=payload.field_type,
    storage_target=payload.storage_target,
    is_sensitive=payload.is_sensitive,
    config=payload.config,
    is_active=payload.is_active,
  )
  return ProfileFieldDefinitionRead.model_validate(definition)


@router.get(
  "/profile-field-definitions/{definition_id}/permissions",
  response_model=list[ProfileFieldPermissionRead],
)
async def list_profile_field_permissions(
  definition_id: UUID,
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> list[ProfileFieldPermissionRead]:
  permissions = await profile_field_policy_service.list_permissions(
    actor=actor,
    field_definition_id=definition_id,
  )
  return [ProfileFieldPermissionRead.model_validate(permission) for permission in permissions]


@router.post(
  "/profile-field-permissions",
  response_model=ProfileFieldPermissionRead,
  status_code=status.HTTP_201_CREATED,
)
async def create_profile_field_permission(
  payload: ProfileFieldPermissionCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> ProfileFieldPermissionRead:
  permission = await profile_field_policy_service.create_permission(
    actor=actor,
    field_definition_id=payload.field_definition_id,
    subject_type=payload.subject_type,
    subject_value=payload.subject_value,
    can_view=payload.can_view,
    can_edit=payload.can_edit,
    scope_filters=payload.scope_filters,
    priority=payload.priority,
  )
  return ProfileFieldPermissionRead.model_validate(permission)


@router.patch("/profile-field-permissions/{permission_id}", response_model=ProfileFieldPermissionRead)
async def update_profile_field_permission(
  permission_id: UUID,
  payload: ProfileFieldPermissionUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_field_policy_service: Annotated[
    ProfileFieldPolicyService,
    Depends(get_profile_field_policy_service),
  ],
) -> ProfileFieldPermissionRead:
  permission = await profile_field_policy_service.update_permission(
    actor=actor,
    permission_id=permission_id,
    subject_type=payload.subject_type,
    subject_value=payload.subject_value,
    can_view=payload.can_view,
    can_edit=payload.can_edit,
    scope_filters=payload.scope_filters,
    priority=payload.priority,
  )
  return ProfileFieldPermissionRead.model_validate(permission)
