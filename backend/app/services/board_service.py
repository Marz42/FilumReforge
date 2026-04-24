from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import UserRole
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.models import BoardCard, BoardCardArchive, Department, User
from app.services.access_control import ensure_active_user, get_actor_department_path_ids


@dataclass(slots=True)
class ScopeOption:
  id: UUID | None
  label: str


class BoardService:
  def __init__(self, session: AsyncSession) -> None:
    self._session = session

  @staticmethod
  def _user_label(user: User) -> str:
    if user.profile is not None and user.profile.real_name:
      return user.profile.real_name
    return user.email

  async def list_publish_scope_options(self, *, actor: User) -> list[ScopeOption]:
    ensure_active_user(actor)
    path_ids = await get_actor_department_path_ids(self._session, actor.id)
    departments = {
      department.id: department
      for department in list(
        await self._session.scalars(
          select(Department).where(Department.id.in_(path_ids)).order_by(Department.sort_order.asc())
        )
      )
    }
    options = [ScopeOption(id=None, label="公司")]
    for department_id in path_ids:
      department = departments.get(department_id)
      if department is not None:
        options.append(ScopeOption(id=department.id, label=department.name))
    return options

  async def _allowed_scope_ids(self, *, actor: User) -> set[UUID | None]:
    scope_ids = set(await get_actor_department_path_ids(self._session, actor.id))
    scope_ids.add(None)
    return scope_ids

  async def list_active_cards(self, *, actor: User) -> list[BoardCard]:
    ensure_active_user(actor)
    scope_ids = await self._allowed_scope_ids(actor=actor)
    statement = (
      select(BoardCard)
      .options(
        selectinload(BoardCard.author).selectinload(User.profile),
        selectinload(BoardCard.scope_department),
      )
      .where(
        BoardCard.expires_at > datetime.now(UTC),
        BoardCard.scope_department_id.in_([scope_id for scope_id in scope_ids if scope_id is not None]),
      )
      .order_by(BoardCard.expires_at.asc(), BoardCard.created_at.desc())
    )
    scoped_cards = list(await self._session.scalars(statement))

    if None in scope_ids:
      company_cards = list(
        await self._session.scalars(
          select(BoardCard)
          .options(
            selectinload(BoardCard.author).selectinload(User.profile),
            selectinload(BoardCard.scope_department),
          )
          .where(
            BoardCard.expires_at > datetime.now(UTC),
            BoardCard.scope_department_id.is_(None),
          )
          .order_by(BoardCard.expires_at.asc(), BoardCard.created_at.desc())
        )
      )
      scoped_cards = company_cards + scoped_cards

    return scoped_cards

  async def list_archives(self, *, actor: User) -> list[BoardCardArchive]:
    ensure_active_user(actor)
    scope_ids = await self._allowed_scope_ids(actor=actor)
    statement = (
      select(BoardCardArchive)
      .options(
        selectinload(BoardCardArchive.author).selectinload(User.profile),
        selectinload(BoardCardArchive.scope_department),
      )
      .order_by(BoardCardArchive.archived_at.desc())
    )
    non_null_scope_ids = [scope_id for scope_id in scope_ids if scope_id is not None]
    if non_null_scope_ids:
      statement = statement.where(
        (BoardCardArchive.scope_department_id.in_(non_null_scope_ids))
        | (BoardCardArchive.scope_department_id.is_(None))
      )
    else:
      statement = statement.where(BoardCardArchive.scope_department_id.is_(None))
    return list(await self._session.scalars(statement))

  async def create_card(
    self,
    *,
    actor: User,
    scope_department_id: UUID | None,
    title: str,
    content_md: str,
  ) -> BoardCard:
    ensure_active_user(actor)
    allowed_scope_ids = await self._allowed_scope_ids(actor=actor)
    if scope_department_id not in allowed_scope_ids:
      raise AuthorizationError("当前账号不能向该范围发布看板卡片。")

    active_count = await self._session.scalar(
      select(func.count(BoardCard.id)).where(
        BoardCard.author_user_id == actor.id,
        BoardCard.expires_at > datetime.now(UTC),
      )
    )
    if (active_count or 0) >= 2:
      raise ConflictError("每个用户同时最多只能发布 2 张有效看板卡片。")

    if scope_department_id is not None and await self._session.get(Department, scope_department_id) is None:
      raise NotFoundError("看板范围部门不存在。")

    card = BoardCard(
      scope_department_id=scope_department_id,
      author_user_id=actor.id,
      title=title.strip(),
      content_md=content_md.strip(),
      expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    self._session.add(card)
    await self._session.commit()
    await self._session.refresh(card)
    return await self._session.scalar(
      select(BoardCard)
      .options(
        selectinload(BoardCard.author).selectinload(User.profile),
        selectinload(BoardCard.scope_department),
      )
      .where(BoardCard.id == card.id)
    )

  async def archive_expired_cards(self) -> int:
    expired_cards = list(
      await self._session.scalars(
        select(BoardCard)
        .where(BoardCard.expires_at <= datetime.now(UTC))
        .order_by(BoardCard.expires_at.asc())
      )
    )
    if not expired_cards:
      return 0

    archived_at = datetime.now(UTC)
    for card in expired_cards:
      self._session.add(
        BoardCardArchive(
          original_card_id=card.id,
          scope_department_id=card.scope_department_id,
          author_user_id=card.author_user_id,
          title=card.title,
          content_md=card.content_md,
          published_at=card.created_at,
          expires_at=card.expires_at,
          archived_at=archived_at,
        )
      )

    await self._session.execute(delete(BoardCard).where(BoardCard.id.in_([card.id for card in expired_cards])))
    await self._session.commit()
    return len(expired_cards)

  async def archive_card(self, *, actor: User, card_id: UUID) -> None:
    ensure_active_user(actor)
    if actor.role != UserRole.ADMIN:
      raise AuthorizationError("仅管理员可以归档看板卡片。")

    card = await self._session.scalar(
      select(BoardCard)
      .options(
        selectinload(BoardCard.author).selectinload(User.profile),
        selectinload(BoardCard.scope_department),
      )
      .where(BoardCard.id == card_id)
    )
    if card is None:
      raise NotFoundError("看板卡片不存在。")

    self._session.add(
      BoardCardArchive(
        original_card_id=card.id,
        scope_department_id=card.scope_department_id,
        author_user_id=card.author_user_id,
        title=card.title,
        content_md=card.content_md,
        published_at=card.created_at,
        expires_at=card.expires_at,
        archived_at=datetime.now(UTC),
      )
    )
    await self._session.execute(delete(BoardCard).where(BoardCard.id == card.id))
    await self._session.commit()
