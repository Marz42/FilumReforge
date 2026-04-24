from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
  get_announcement_service,
  get_board_service,
  get_current_user,
  get_overview_service,
)
from app.models import User
from app.schemas.overview import (
  AnnouncementCreateRequest,
  AnnouncementRead,
  BoardCardCreateRequest,
  BoardCardRead,
  OverviewPermissionsRead,
  OverviewRead,
  OverviewScopeOptionRead,
  OverviewTaskInboxItemRead,
  OverviewTaskTrackingItemRead,
)
from app.services.announcement_service import AnnouncementService
from app.services.board_service import BoardService
from app.services.overview_service import OverviewService

router = APIRouter()


@router.get("/overview", response_model=OverviewRead)
async def read_overview(
  actor: Annotated[User, Depends(get_current_user)],
  overview_service: Annotated[OverviewService, Depends(get_overview_service)],
) -> OverviewRead:
  snapshot = await overview_service.get_overview(actor=actor)
  return OverviewRead(
    board_cards=[
      BoardCardRead(
        id=card.id,
        scope_department_id=card.scope_department_id,
        scope_label=card.scope_department.name if card.scope_department is not None else "公司",
        author_user_id=card.author_user_id,
        author_label=card.author.profile.real_name if card.author and card.author.profile and card.author.profile.real_name else card.author.email,
        title=card.title,
        content_md=card.content_md,
        expires_at=card.expires_at,
        created_at=card.created_at,
      )
      for card in snapshot.board_cards
    ],
    announcements=[
      AnnouncementRead(
        id=announcement.id,
        publisher_department_id=announcement.publisher_department_id,
        publisher_department_name=announcement.publisher_department.name,
        author_user_id=announcement.author_user_id,
        author_label=announcement.author.profile.real_name if announcement.author and announcement.author.profile and announcement.author.profile.real_name else announcement.author.email,
        title=announcement.title,
        content_md=announcement.content_md,
        published_at=announcement.published_at,
        created_at=announcement.created_at,
      )
      for announcement in snapshot.announcements
    ],
    task_inbox=[
      OverviewTaskInboxItemRead(
        task_id=item.task_id,
        title=item.title,
        priority=item.priority,
        status=item.status,
        due_date=item.due_date,
        department_name=item.department_name,
        current_stage_label=item.current_stage_label,
        current_handler_label=item.current_handler_label,
      )
      for item in snapshot.task_inbox
    ],
    task_tracking=[
      OverviewTaskTrackingItemRead(
        task_id=item.task_id,
        title=item.title,
        priority=item.priority,
        status=item.status,
        due_date=item.due_date,
        department_name=item.department_name,
        relation_types=item.relation_types,
        current_stage_label=item.current_stage_label,
        current_handler_label=item.current_handler_label,
      )
      for item in snapshot.task_tracking
    ],
    permissions=OverviewPermissionsRead(
      board_scope_options=[
        OverviewScopeOptionRead(id=option.id, label=option.label)
        for option in snapshot.board_scope_options
      ],
      announcement_scope_options=[
        OverviewScopeOptionRead(id=option.id, label=option.label)
        for option in snapshot.announcement_scope_options
      ],
      can_publish_board=bool(snapshot.board_scope_options),
      can_publish_announcement=snapshot.can_publish_announcement,
    ),
  )


@router.post("/board-cards", response_model=BoardCardRead, status_code=status.HTTP_201_CREATED)
async def create_board_card(
  payload: BoardCardCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  board_service: Annotated[BoardService, Depends(get_board_service)],
) -> BoardCardRead:
  card = await board_service.create_card(
    actor=actor,
    scope_department_id=payload.scope_department_id,
    title=payload.title,
    content_md=payload.content_md,
  )
  return BoardCardRead(
    id=card.id,
    scope_department_id=card.scope_department_id,
    scope_label=card.scope_department.name if card.scope_department is not None else "公司",
    author_user_id=card.author_user_id,
    author_label=card.author.profile.real_name if card.author and card.author.profile and card.author.profile.real_name else card.author.email,
    title=card.title,
    content_md=card.content_md,
    expires_at=card.expires_at,
    created_at=card.created_at,
  )


@router.get("/board-cards/archives", response_model=list[BoardCardRead])
async def list_board_card_archives(
  actor: Annotated[User, Depends(get_current_user)],
  board_service: Annotated[BoardService, Depends(get_board_service)],
) -> list[BoardCardRead]:
  archives = await board_service.list_archives(actor=actor)
  return [
    BoardCardRead(
      id=archive.id,
      scope_department_id=archive.scope_department_id,
      scope_label=archive.scope_department.name if archive.scope_department is not None else "公司",
      author_user_id=archive.author_user_id,
      author_label=archive.author.profile.real_name if archive.author and archive.author.profile and archive.author.profile.real_name else archive.author.email,
      title=archive.title,
      content_md=archive.content_md,
      expires_at=archive.expires_at,
      created_at=archive.published_at,
    )
    for archive in archives
  ]


@router.post("/board-cards/{card_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_board_card(
  card_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  board_service: Annotated[BoardService, Depends(get_board_service)],
) -> Response:
  await board_service.archive_card(actor=actor, card_id=card_id)
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/announcements", response_model=AnnouncementRead, status_code=status.HTTP_201_CREATED)
async def create_announcement(
  payload: AnnouncementCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  announcement_service: Annotated[AnnouncementService, Depends(get_announcement_service)],
) -> AnnouncementRead:
  announcement = await announcement_service.create_announcement(
    actor=actor,
    publisher_department_id=payload.publisher_department_id,
    title=payload.title,
    content_md=payload.content_md,
  )
  return AnnouncementRead(
    id=announcement.id,
    publisher_department_id=announcement.publisher_department_id,
    publisher_department_name=announcement.publisher_department.name,
    author_user_id=announcement.author_user_id,
    author_label=announcement.author.profile.real_name if announcement.author and announcement.author.profile and announcement.author.profile.real_name else announcement.author.email,
    title=announcement.title,
    content_md=announcement.content_md,
    published_at=announcement.published_at,
    created_at=announcement.created_at,
  )


@router.get("/announcement-archives", response_model=list[AnnouncementRead])
async def list_announcement_archives(
  actor: Annotated[User, Depends(get_current_user)],
  announcement_service: Annotated[AnnouncementService, Depends(get_announcement_service)],
) -> list[AnnouncementRead]:
  archives = await announcement_service.list_archives(actor=actor)
  return [
    AnnouncementRead(
      id=archive.id,
      publisher_department_id=archive.publisher_department_id,
      publisher_department_name=archive.publisher_department.name,
      author_user_id=archive.author_user_id,
      author_label=archive.author.profile.real_name if archive.author and archive.author.profile and archive.author.profile.real_name else archive.author.email,
      title=archive.title,
      content_md=archive.content_md,
      published_at=archive.published_at,
      created_at=archive.published_at,
    )
    for archive in archives
  ]


@router.post("/announcements/{announcement_id}/withdraw", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_announcement(
  announcement_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  announcement_service: Annotated[AnnouncementService, Depends(get_announcement_service)],
) -> Response:
  await announcement_service.withdraw_announcement(actor=actor, announcement_id=announcement_id)
  return Response(status_code=status.HTTP_204_NO_CONTENT)
