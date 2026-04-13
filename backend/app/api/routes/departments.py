from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_department_service, get_management_user
from app.models import User
from app.schemas.departments import (
  DepartmentCreateRequest,
  DepartmentRead,
  DepartmentTreeNode,
  DepartmentUpdateRequest,
)
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments")


@router.get("", response_model=list[DepartmentRead])
async def list_departments(
  actor: Annotated[User, Depends(get_current_user)],
  department_service: Annotated[DepartmentService, Depends(get_department_service)],
) -> list[DepartmentRead]:
  departments = await department_service.list_departments(actor=actor)
  return [DepartmentRead.model_validate(department) for department in departments]


@router.get("/tree", response_model=list[DepartmentTreeNode])
async def read_department_tree(
  actor: Annotated[User, Depends(get_current_user)],
  department_service: Annotated[DepartmentService, Depends(get_department_service)],
) -> list[DepartmentTreeNode]:
  departments = await department_service.list_departments(actor=actor)
  tree = department_service.build_tree(departments)
  return [DepartmentTreeNode.model_validate(node) for node in tree]


@router.get("/{department_id}", response_model=DepartmentRead)
async def read_department(
  department_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  department_service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
  department = await department_service.get_department(actor=actor, department_id=department_id)
  return DepartmentRead.model_validate(department)


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
  payload: DepartmentCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  department_service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
  department = await department_service.create_department(
    actor=actor,
    name=payload.name,
    code=payload.code,
    parent_id=payload.parent_id,
    manager_id=payload.manager_id,
    sort_order=payload.sort_order,
  )
  return DepartmentRead.model_validate(department)


@router.patch("/{department_id}", response_model=DepartmentRead)
async def update_department(
  department_id: UUID,
  payload: DepartmentUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  department_service: Annotated[DepartmentService, Depends(get_department_service)],
) -> DepartmentRead:
  department = await department_service.update_department(
    actor=actor,
    department_id=department_id,
    name=payload.name,
    code=payload.code,
    parent_id=payload.parent_id,
    manager_id=payload.manager_id,
    sort_order=payload.sort_order,
    is_active=payload.is_active,
  )
  return DepartmentRead.model_validate(department)
