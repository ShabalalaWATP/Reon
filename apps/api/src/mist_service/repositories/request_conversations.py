"""Persistence queries for structured request conversations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mist_service.conversation_models import (
    RequestConversation,
    RequestConversationDelivery,
    RequestConversationMessage,
)
from mist_service.domain import Actor
from mist_service.identity_context import active_actor_condition
from mist_service.models import ServiceRequest, User, UserRole
from mist_service.organisation_models import (
    OrganisationUnit,
    RequestRouteSelection,
)
from mist_service.qc_membership import (
    live_qc_manager_condition,
    live_qc_membership_condition,
)
from mist_service.request_participant_models import RequestParticipant
from mist_service.team_models import TeamMembership, WorkspacePosition


class RequestConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request(self, request_id: UUID) -> ServiceRequest | None:
        return await self.session.get(ServiceRequest, request_id)

    async def lock_request(self, request_id: UUID) -> ServiceRequest | None:
        return cast(
            ServiceRequest | None,
            await self.session.scalar(
                select(ServiceRequest)
                .where(ServiceRequest.id == request_id)
                .with_for_update()
            ),
        )

    async def active_actor(self, actor: Actor) -> bool:
        return (
            await self.session.scalar(
                select(User.id).where(active_actor_condition(actor))
            )
            is not None
        )

    async def is_active_participant(
        self, request: ServiceRequest, actor: Actor
    ) -> bool:
        if (
            actor.role is not UserRole.DELIVERY_SPECIALIST
            or request.assigned_delivery_team_id is None
        ):
            return False
        now = datetime.now(UTC)
        return (
            await self.session.scalar(
                select(RequestParticipant.id)
                .join(User, User.id == RequestParticipant.user_id)
                .join(
                    TeamMembership,
                    and_(
                        TeamMembership.user_id == RequestParticipant.user_id,
                        TeamMembership.team_id == request.assigned_delivery_team_id,
                    ),
                )
                .where(
                    RequestParticipant.request_id == request.id,
                    RequestParticipant.user_id == actor.id,
                    RequestParticipant.effective_from <= now,
                    RequestParticipant.ended_at.is_(None),
                    User.is_active.is_(True),
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                )
            )
            is not None
        )

    async def is_active_team_manager(
        self, request: ServiceRequest, actor: Actor
    ) -> bool:
        return bool(
            request.assigned_delivery_team_id is not None
            and actor.role is UserRole.DELIVERY_TEAM_LEAD
            and actor.id
            in await self.active_team_manager_ids(request.assigned_delivery_team_id)
        )

    async def is_active_qc_member(self, actor: Actor) -> bool:
        return await self._is_active_qc(actor, manager=False)

    async def is_active_qc_manager(self, actor: Actor) -> bool:
        return await self._is_active_qc(actor, manager=True)

    async def _is_active_qc(self, actor: Actor, *, manager: bool) -> bool:
        if actor.role is not UserRole.QUALITY_RELEASE:
            return False
        now = datetime.now(UTC)
        condition = (
            live_qc_manager_condition(cast(ColumnElement[UUID], User.id), now)
            if manager
            else live_qc_membership_condition(cast(ColumnElement[UUID], User.id), now)
        )
        return (
            await self.session.scalar(
                select(User.id).where(
                    active_actor_condition(actor),
                    condition,
                )
            )
            is not None
        )

    async def selected_route(
        self, request_id: UUID
    ) -> list[tuple[OrganisationUnit, int]]:
        rows = (
            await self.session.execute(
                select(OrganisationUnit, RequestRouteSelection.position)
                .join(
                    RequestRouteSelection,
                    RequestRouteSelection.unit_id == OrganisationUnit.id,
                )
                .where(RequestRouteSelection.request_id == request_id)
                .order_by(RequestRouteSelection.position)
            )
        ).all()
        return [(row.OrganisationUnit, row.position) for row in rows]

    async def conversation(
        self, request_id: UUID, conversation_id: UUID
    ) -> RequestConversation | None:
        return cast(
            RequestConversation | None,
            await self.session.scalar(
                select(RequestConversation)
                .where(
                    RequestConversation.id == conversation_id,
                    RequestConversation.request_id == request_id,
                )
                .execution_options(populate_existing=True)
            ),
        )

    async def mutation_message(
        self, sender_id: UUID, client_mutation_id: UUID
    ) -> RequestConversationMessage | None:
        return cast(
            RequestConversationMessage | None,
            await self.session.scalar(
                select(RequestConversationMessage)
                .where(
                    RequestConversationMessage.sender_user_id == sender_id,
                    RequestConversationMessage.client_mutation_id == client_mutation_id,
                )
                .options(
                    selectinload(RequestConversationMessage.sender),
                    selectinload(RequestConversationMessage.deliveries),
                    selectinload(RequestConversationMessage.request_event),
                    selectinload(RequestConversationMessage.conversation),
                )
            ),
        )

    async def first_message_id(self, conversation_id: UUID) -> UUID | None:
        return cast(
            UUID | None,
            await self.session.scalar(
                select(RequestConversationMessage.id)
                .where(RequestConversationMessage.conversation_id == conversation_id)
                .order_by(
                    RequestConversationMessage.created_at,
                    RequestConversationMessage.id,
                )
                .limit(1)
            ),
        )

    async def message_in_conversation(
        self, conversation_id: UUID, message_id: UUID
    ) -> RequestConversationMessage | None:
        return cast(
            RequestConversationMessage | None,
            await self.session.scalar(
                select(RequestConversationMessage).where(
                    RequestConversationMessage.id == message_id,
                    RequestConversationMessage.conversation_id == conversation_id,
                )
            ),
        )

    async def active_participant_ids(self, request: ServiceRequest) -> set[UUID]:
        if request.assigned_delivery_team_id is None:
            return set()
        now = datetime.now(UTC)
        return set(
            await self.session.scalars(
                select(RequestParticipant.user_id)
                .join(User, User.id == RequestParticipant.user_id)
                .join(
                    TeamMembership,
                    and_(
                        TeamMembership.user_id == RequestParticipant.user_id,
                        TeamMembership.team_id == request.assigned_delivery_team_id,
                    ),
                )
                .where(
                    RequestParticipant.request_id == request.id,
                    RequestParticipant.effective_from <= now,
                    RequestParticipant.ended_at.is_(None),
                    User.is_active.is_(True),
                    User.role == UserRole.DELIVERY_SPECIALIST,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                )
            )
        )

    async def active_team_manager_ids(self, team_id: UUID) -> set[UUID]:
        now = datetime.now(UTC)
        return set(
            await self.session.scalars(
                select(TeamMembership.user_id)
                .join(User, User.id == TeamMembership.user_id)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.workspace_position == WorkspacePosition.MANAGER,
                    TeamMembership.effective_from <= now,
                    or_(
                        TeamMembership.effective_until.is_(None),
                        TeamMembership.effective_until > now,
                    ),
                    User.is_active.is_(True),
                )
            )
        )

    async def active_unit_member_ids(
        self, unit_id: UUID, role: UserRole | None = None
    ) -> set[UUID]:
        now = datetime.now(UTC)
        query = (
            select(TeamMembership.user_id)
            .join(User, User.id == TeamMembership.user_id)
            .where(
                TeamMembership.team_id == unit_id,
                TeamMembership.effective_from <= now,
                or_(
                    TeamMembership.effective_until.is_(None),
                    TeamMembership.effective_until > now,
                ),
                User.is_active.is_(True),
            )
        )
        if role is not None:
            query = query.where(User.role == role)
        return set(await self.session.scalars(query))

    async def active_qc_ids(self, *, manager_only: bool = False) -> set[UUID]:
        now = datetime.now(UTC)
        condition = (
            live_qc_manager_condition(cast(ColumnElement[UUID], User.id), now)
            if manager_only
            else live_qc_membership_condition(cast(ColumnElement[UUID], User.id), now)
        )
        return set(
            await self.session.scalars(
                select(User.id).where(
                    User.role == UserRole.QUALITY_RELEASE,
                    User.is_active.is_(True),
                    condition,
                )
            )
        )

    async def add_message(
        self,
        conversation: RequestConversation | None,
        message: RequestConversationMessage,
        recipient_ids: set[UUID],
    ) -> None:
        if conversation is not None:
            self.session.add(conversation)
        self.session.add(message)
        self.session.add_all(
            RequestConversationDelivery(
                message_id=message.id,
                recipient_user_id=recipient_id,
            )
            for recipient_id in sorted(recipient_ids, key=str)
            if recipient_id != message.sender_user_id
        )
        await self.session.flush()

    async def mark_read(
        self, conversation_id: UUID, recipient_id: UUID, at: datetime
    ) -> None:
        message_ids = select(RequestConversationMessage.id).where(
            RequestConversationMessage.conversation_id == conversation_id
        )
        await self.session.execute(
            update(RequestConversationDelivery)
            .where(
                RequestConversationDelivery.message_id.in_(message_ids),
                RequestConversationDelivery.recipient_user_id == recipient_id,
                RequestConversationDelivery.read_at.is_(None),
            )
            .values(read_at=at)
        )
