"""Bounded SQL pages and admission counts for request conversations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.sql.elements import ColumnElement

from mist_service.conversation_models import (
    ConversationTargetType,
    RequestConversation,
    RequestConversationDelivery,
    RequestConversationMessage,
)
from mist_service.conversation_page_types import ConversationPage, MessagePage
from mist_service.projection_pagination import encode_cursor
from mist_service.request_event_audience import RequestEventAudience


class RequestConversationPageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def conversations(
        self,
        request_id: UUID,
        *,
        customer_only: bool,
        allowed_targets: set[ConversationTargetType],
        route_unit_ids: set[UUID],
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> ConversationPage:
        visible = (
            RequestConversation.visibility == RequestEventAudience.CUSTOMER_AND_STAFF
        )
        if not customer_only:
            internal: list[ColumnElement[bool]] = []
            if allowed_targets:
                internal.append(RequestConversation.target_type.in_(allowed_targets))
            if route_unit_ids:
                internal.append(
                    and_(
                        RequestConversation.target_type
                        == ConversationTargetType.ROUTE_UNIT,
                        RequestConversation.target_unit_id.in_(route_unit_ids),
                    )
                )
            visible = or_(visible, *internal)
        query = select(RequestConversation).where(
            RequestConversation.request_id == request_id, visible
        )
        if cursor is not None:
            changed_at, item_id = cursor
            query = query.where(
                self._cursor_condition(
                    RequestConversation.created_at,
                    RequestConversation.id,
                    changed_at,
                    item_id,
                )
            )
        rows = list(
            await self.session.scalars(
                query.order_by(
                    RequestConversation.created_at.desc(), RequestConversation.id.desc()
                ).limit(limit + 1)
            )
        )
        items = rows[:limit]
        next_cursor = (
            encode_cursor(items[-1].created_at, items[-1].id)
            if len(rows) > limit and items
            else None
        )
        return ConversationPage(items, next_cursor)

    async def messages(
        self,
        conversation_id: UUID,
        *,
        limit: int,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> MessagePage:
        query = select(RequestConversationMessage).where(
            RequestConversationMessage.conversation_id == conversation_id
        )
        if cursor is not None:
            changed_at, item_id = cursor
            query = query.where(
                self._cursor_condition(
                    RequestConversationMessage.created_at,
                    RequestConversationMessage.id,
                    changed_at,
                    item_id,
                )
            )
        rows = list(
            await self.session.scalars(
                query.options(
                    selectinload(RequestConversationMessage.sender),
                    selectinload(RequestConversationMessage.deliveries),
                    selectinload(RequestConversationMessage.request_event),
                )
                .order_by(
                    RequestConversationMessage.created_at.desc(),
                    RequestConversationMessage.id.desc(),
                )
                .limit(limit + 1)
            )
        )
        newest_first = rows[:limit]
        next_cursor = (
            encode_cursor(newest_first[-1].created_at, newest_first[-1].id)
            if len(rows) > limit and newest_first
            else None
        )
        return MessagePage(list(reversed(newest_first)), next_cursor)

    async def message_pages(
        self, conversation_ids: list[UUID], *, limit: int
    ) -> dict[UUID, MessagePage]:
        """Load a bounded newest-message window for every conversation at once."""

        if not conversation_ids:
            return {}
        rows = list(
            await self.session.scalars(
                bounded_message_query(conversation_ids, limit=limit)
            )
        )
        grouped: dict[UUID, list[RequestConversationMessage]] = {
            conversation_id: [] for conversation_id in conversation_ids
        }
        for message in rows:
            grouped[message.conversation_id].append(message)
        pages: dict[UUID, MessagePage] = {}
        for conversation_id, messages in grouped.items():
            newest_first = sorted(
                messages,
                key=lambda item: (item.created_at, item.id),
                reverse=True,
            )
            visible = newest_first[:limit]
            pages[conversation_id] = MessagePage(
                items=list(reversed(visible)),
                next_cursor=(
                    encode_cursor(visible[-1].created_at, visible[-1].id)
                    if len(newest_first) > limit and visible
                    else None
                ),
            )
        return pages

    async def unread_counts(
        self, conversation_ids: list[UUID], actor_id: UUID
    ) -> dict[UUID, int]:
        """Return complete unread totals, independent of message page size."""

        if not conversation_ids:
            return {}
        rows = (
            await self.session.execute(
                select(
                    RequestConversationMessage.conversation_id,
                    func.count(RequestConversationDelivery.id),
                )
                .join(
                    RequestConversationDelivery,
                    RequestConversationDelivery.message_id
                    == RequestConversationMessage.id,
                )
                .where(
                    RequestConversationMessage.conversation_id.in_(conversation_ids),
                    RequestConversationDelivery.recipient_user_id == actor_id,
                    RequestConversationDelivery.read_at.is_(None),
                )
                .group_by(RequestConversationMessage.conversation_id)
            )
        ).all()
        return {conversation_id: int(count) for conversation_id, count in rows}

    async def admission_counts(
        self, request_id: UUID, actor_id: UUID
    ) -> tuple[int, int, int]:
        conversations = await self._count(
            select(func.count(RequestConversation.id)).where(
                RequestConversation.request_id == request_id
            )
        )
        request_messages = await self._count(
            select(func.count(RequestConversationMessage.id))
            .join(RequestConversation)
            .where(RequestConversation.request_id == request_id)
        )
        actor_messages = await self._count(
            select(func.count(RequestConversationMessage.id))
            .join(RequestConversation)
            .where(
                RequestConversation.request_id == request_id,
                RequestConversationMessage.sender_user_id == actor_id,
            )
        )
        return conversations, request_messages, actor_messages

    async def _count(self, query: Select[tuple[int]]) -> int:
        return int(await self.session.scalar(query) or 0)

    def _cursor_condition(
        self,
        timestamp: InstrumentedAttribute[datetime],
        item_key: InstrumentedAttribute[UUID],
        changed_at: datetime,
        item_id: UUID,
    ) -> ColumnElement[bool]:
        if self.session.get_bind().dialect.name == "sqlite":
            timestamp_value = func.julianday(timestamp)
            cursor_value = func.julianday(changed_at)
            return or_(
                timestamp_value < cursor_value,
                and_(timestamp_value == cursor_value, item_key < item_id),
            )
        return or_(
            timestamp < changed_at,
            and_(timestamp == changed_at, item_key < item_id),
        )


def bounded_message_query(
    conversation_ids: list[UUID], *, limit: int
) -> Select[tuple[RequestConversationMessage]]:
    """Build the portable per-conversation message-window query."""

    rank = func.row_number().over(
        partition_by=RequestConversationMessage.conversation_id,
        order_by=(
            RequestConversationMessage.created_at.desc(),
            RequestConversationMessage.id.desc(),
        ),
    )
    ranked = (
        select(
            RequestConversationMessage.id.label("message_id"),
            rank.label("message_rank"),
        )
        .where(RequestConversationMessage.conversation_id.in_(conversation_ids))
        .subquery()
    )
    return (
        select(RequestConversationMessage)
        .join(ranked, ranked.c.message_id == RequestConversationMessage.id)
        .where(ranked.c.message_rank <= limit + 1)
        .options(
            selectinload(RequestConversationMessage.sender),
            selectinload(RequestConversationMessage.deliveries),
            selectinload(RequestConversationMessage.request_event),
        )
    )
