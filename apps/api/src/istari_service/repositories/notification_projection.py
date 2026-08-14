"""Transactional notification event publication and recipient projection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.action_notification_models import (
    NotificationEvent,
    NotificationEventGroup,
    NotificationProjectionStatus,
    NotificationRecipient,
)
from istari_service.errors import ObjectNotFound
from istari_service.models import User, UserRole
from istari_service.notification_ports import RecipientRule
from istari_service.notification_preference_policy import (
    disabled_recipient_contexts,
    required_context,
    role_is_current,
)
from istari_service.operational_analytics_projection import (
    project_notification_sent_fact,
)
from istari_service.qc_membership import QC_TEAM_ID
from istari_service.repositories.notification_projection_checkpoint import (
    update_notification_checkpoint,
)
from istari_service.team_models import TeamMembership, WorkspacePosition


class SqlAlchemyNotificationProjectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_event(
        self,
        *,
        stable_key: str,
        event_type: str,
        event_group: NotificationEventGroup,
        source_version: int,
        request_id: UUID | None,
        safe_subject: str,
        deep_link: str | None,
        audience: list[dict[str, str | None]],
        occurred_at: datetime,
    ) -> NotificationEvent:
        existing = await self.session.scalar(
            select(NotificationEvent).where(NotificationEvent.stable_key == stable_key)
        )
        if existing is not None:
            return existing
        event = NotificationEvent(
            stable_key=stable_key,
            event_type=event_type.strip().upper(),
            event_group=event_group,
            source_version=source_version,
            request_id=request_id,
            safe_subject=safe_subject.strip(),
            deep_link=deep_link,
            audience=audience,
            occurred_at=occurred_at,
            status=NotificationProjectionStatus.PENDING,
            attempts=0,
            available_at=occurred_at,
        )
        self.session.add(event)
        await self.session.flush()
        await project_notification_sent_fact(self.session, event)
        return event

    async def pending_events(
        self, *, limit: int, available_at: datetime
    ) -> list[NotificationEvent]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationEvent)
                    .where(
                        NotificationEvent.status.in_(
                            [
                                NotificationProjectionStatus.PENDING,
                                NotificationProjectionStatus.FAILED,
                            ]
                        ),
                        NotificationEvent.available_at <= available_at,
                    )
                    .order_by(NotificationEvent.available_at, NotificationEvent.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

    async def project_event(
        self,
        event_id: UUID,
        recipients: list[RecipientRule],
        *,
        projected_at: datetime,
        update_checkpoint: bool = True,
    ) -> list[NotificationRecipient]:
        event = await self.session.scalar(
            select(NotificationEvent)
            .where(NotificationEvent.id == event_id)
            .with_for_update()
        )
        if event is None:
            raise ObjectNotFound()
        if event.status is NotificationProjectionStatus.PROJECTED:
            return await self._event_recipients(event.id)
        event.attempts += 1
        created: list[NotificationRecipient] = []
        current_rules = await self._current_recipient_rules(recipients)
        disabled = await disabled_recipient_contexts(
            self.session,
            current_rules,
            event.event_group,
            event.event_type,
        )
        existing = await self._recipients_by_user(
            event.id,
            {rule.user_id for rule in current_rules},
        )
        added = False
        for rule in current_rules:
            if (rule.user_id, required_context(rule.required_role)) in disabled:
                continue
            recipient = existing.get(rule.user_id)
            if recipient is None:
                recipient = NotificationRecipient(
                    notification_event_id=event.id,
                    recipient_user_id=rule.user_id,
                    idempotency_key=f"{event.stable_key}:{rule.user_id}",
                    access_kind=rule.access_kind,
                    required_role=rule.required_role,
                    required_scope=rule.required_scope,
                    organisation_unit_id=rule.organisation_unit_id,
                    version=1,
                )
                self.session.add(recipient)
                added = True
            created.append(recipient)
        if added:
            await self.session.flush()
        event.status = NotificationProjectionStatus.PROJECTED
        event.projected_at = projected_at
        event.last_error = None
        unit_id = next(
            (
                item.organisation_unit_id
                for item in created
                if item.organisation_unit_id
            ),
            None,
        )
        await project_notification_sent_fact(self.session, event, unit_id=unit_id)
        if update_checkpoint:
            await update_notification_checkpoint(
                self.session, event, projected_at, failed=False
            )
        return created

    async def update_projection_checkpoint(
        self,
        event: NotificationEvent,
        *,
        projected_at: datetime,
    ) -> None:
        """Refresh batch health once after all selected events are projected."""

        await update_notification_checkpoint(
            self.session, event, projected_at, failed=False
        )

    async def mark_projection_failed(
        self, event_id: UUID, *, error_code: str, attempted_at: datetime
    ) -> None:
        event = await self.session.scalar(
            select(NotificationEvent)
            .where(NotificationEvent.id == event_id)
            .with_for_update()
        )
        if event is None:
            raise ObjectNotFound()
        event.attempts += 1
        event.status = NotificationProjectionStatus.FAILED
        event.last_error = error_code[:120]
        event.available_at = attempted_at
        await update_notification_checkpoint(
            self.session, event, attempted_at, failed=True
        )

    async def _event_recipients(self, event_id: UUID) -> list[NotificationRecipient]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationRecipient).where(
                        NotificationRecipient.notification_event_id == event_id
                    )
                )
            ).all()
        )

    async def _current_recipient_rules(
        self, recipients: list[RecipientRule]
    ) -> list[RecipientRule]:
        unique_by_user: dict[UUID, RecipientRule] = {}
        for rule in recipients:
            unique_by_user.setdefault(rule.user_id, rule)
        unique = list(unique_by_user.values())
        if not unique:
            return []
        user_ids = {rule.user_id for rule in unique}
        users = {
            user_id: (role, scope, customer_context_enabled)
            for user_id, role, scope, customer_context_enabled in (
                (
                    await self.session.execute(
                        select(
                            User.id,
                            User.role,
                            User.scope,
                            User.customer_context_enabled,
                        ).where(
                            User.id.in_(user_ids),
                            User.is_active.is_(True),
                        )
                    )
                )
                .tuples()
                .all()
            )
        }
        required_memberships = {
            (rule.user_id, rule.organisation_unit_id)
            for rule in unique
            if rule.organisation_unit_id is not None
        }
        required_memberships.update(
            (rule.user_id, QC_TEAM_ID)
            for rule in unique
            if rule.required_role is UserRole.QUALITY_RELEASE
        )
        current_memberships: set[tuple[UUID, UUID]] = set()
        if required_memberships:
            membership_users = {user_id for user_id, _unit_id in required_memberships}
            membership_units = {unit_id for _user_id, unit_id in required_memberships}
            current_memberships = set(
                (
                    await self.session.execute(
                        select(
                            TeamMembership.user_id,
                            TeamMembership.team_id,
                        ).where(
                            TeamMembership.user_id.in_(membership_users),
                            TeamMembership.team_id.in_(membership_units),
                            TeamMembership.effective_from <= datetime.now(UTC),
                            or_(
                                TeamMembership.effective_until.is_(None),
                                TeamMembership.effective_until > datetime.now(UTC),
                            ),
                            or_(
                                TeamMembership.team_id != QC_TEAM_ID,
                                TeamMembership.workspace_position
                                == WorkspacePosition.MANAGER,
                            ),
                        )
                    )
                )
                .tuples()
                .all()
            )
        return [
            rule
            for rule in unique
            if self._rule_is_current(rule, users, current_memberships)
        ]

    @staticmethod
    def _rule_is_current(
        rule: RecipientRule,
        users: dict[UUID, tuple[UserRole, str, bool]],
        memberships: set[tuple[UUID, UUID]],
    ) -> bool:
        user = users.get(rule.user_id)
        if user is None or not role_is_current(rule.required_role, user):
            return False
        if rule.required_role is UserRole.QUALITY_RELEASE:
            return (rule.user_id, QC_TEAM_ID) in memberships
        if rule.organisation_unit_id is not None:
            return (rule.user_id, rule.organisation_unit_id) in memberships
        return rule.required_scope is None or user[1] == rule.required_scope

    async def _recipients_by_user(
        self,
        event_id: UUID,
        user_ids: set[UUID],
    ) -> dict[UUID, NotificationRecipient]:
        if not user_ids:
            return {}
        return {
            recipient.recipient_user_id: recipient
            for recipient in await self.session.scalars(
                select(NotificationRecipient).where(
                    NotificationRecipient.notification_event_id == event_id,
                    NotificationRecipient.recipient_user_id.in_(user_ids),
                )
            )
        }
