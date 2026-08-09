"""SQLAlchemy adapter for private Customer request drafts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.domain import Actor
from istari_service.errors import ObjectNotFound, StaleVersion
from istari_service.models import ServiceRequest
from istari_service.repositories.configuration_pins import (
    SqlAlchemyConfigurationPinRepository,
)
from istari_service.repositories.projection_pagination import (
    decode_cursor,
    encode_cursor,
)
from istari_service.repositories.requests import SqlAlchemyRequestRepository
from istari_service.request_draft_models import RequestDraft
from istari_service.schemas.drafts import (
    RequestDraftCreate,
    RequestDraftSubmit,
    RequestDraftUpdate,
    RequestDraftView,
)
from istari_service.schemas.requests import RequestCreate, RequestDetail


def _view(draft: RequestDraft) -> RequestDraftView:
    return RequestDraftView.model_validate(draft)


class SqlAlchemyDraftRepository:
    def __init__(
        self,
        session: AsyncSession,
        *,
        process_id: str,
        configuration_pins: SqlAlchemyConfigurationPinRepository | None = None,
    ) -> None:
        self._session = session
        self._requests = SqlAlchemyRequestRepository(
            session,
            process_id=process_id,
            configuration_pins=configuration_pins,
        )

    async def list_for_requester(self, requester_id: UUID) -> list[RequestDraftView]:
        items, _cursor = await self.page_for_requester(
            requester_id, limit=100, cursor=None
        )
        return items

    async def page_for_requester(
        self,
        requester_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[RequestDraftView], str | None]:
        statement = select(RequestDraft).where(
            RequestDraft.requester_id == requester_id
        )
        if cursor is not None:
            changed_at, draft_id = decode_cursor(
                cursor, message="The draft filters are invalid."
            )
            statement = statement.where(
                or_(
                    RequestDraft.updated_at < changed_at,
                    and_(
                        RequestDraft.updated_at == changed_at,
                        RequestDraft.id < draft_id,
                    ),
                )
            )
        drafts = list(
            await self._session.scalars(
                statement.order_by(
                    RequestDraft.updated_at.desc(), RequestDraft.id.desc()
                ).limit(limit + 1)
            )
        )
        page = drafts[:limit]
        next_cursor = (
            encode_cursor(page[-1].updated_at, page[-1].id)
            if len(drafts) > limit and page
            else None
        )
        return [_view(draft) for draft in page], next_cursor

    async def get(self, draft_id: UUID, requester_id: UUID) -> RequestDraftView | None:
        draft = await self._session.scalar(
            select(RequestDraft).where(
                RequestDraft.id == draft_id,
                RequestDraft.requester_id == requester_id,
            )
        )
        return _view(draft) if draft else None

    async def create(
        self, actor: Actor, command: RequestDraftCreate
    ) -> RequestDraftView:
        draft = RequestDraft(
            requester_id=actor.id,
            **command.model_dump(exclude_unset=True),
        )
        self._session.add(draft)
        await self._session.flush()
        return _view(draft)

    async def update(
        self,
        draft_id: UUID,
        actor: Actor,
        command: RequestDraftUpdate,
    ) -> RequestDraftView:
        draft = await self._locked(draft_id, actor.id)
        if draft.version != command.expected_version:
            raise StaleVersion()
        changes = command.model_dump(exclude={"expected_version"}, exclude_unset=True)
        for field, value in changes.items():
            setattr(draft, field, value)
        draft.version += 1
        await self._session.flush()
        await self._session.refresh(draft)
        return _view(draft)

    async def delete(
        self, draft_id: UUID, requester_id: UUID, expected_version: int
    ) -> None:
        draft = await self._locked(draft_id, requester_id)
        if draft.version != expected_version:
            raise StaleVersion()
        await self._session.delete(draft)
        await self._session.flush()

    async def submit(
        self,
        draft_id: UUID,
        actor: Actor,
        command: RequestDraftSubmit,
    ) -> RequestDetail:
        existing = await self._session.scalar(
            select(ServiceRequest).where(
                ServiceRequest.submission_key == command.submission_key,
                ServiceRequest.requester_id == actor.id,
            )
        )
        if existing is not None:
            return await self._requests.get_detail(
                existing.id, reveal_unreleased_deliverable=False
            )
        draft = await self._locked(draft_id, actor.id)
        if draft.version != command.expected_version:
            raise StaleVersion()
        request_command = RequestCreate.model_validate(
            command.model_dump(exclude={"expected_version"})
        )
        detail = await self._requests.create(actor, request_command)
        await self._session.delete(draft)
        await self._session.flush()
        return detail

    async def _locked(self, draft_id: UUID, requester_id: UUID) -> RequestDraft:
        draft = await self._session.scalar(
            select(RequestDraft)
            .where(
                RequestDraft.id == draft_id,
                RequestDraft.requester_id == requester_id,
            )
            .with_for_update()
        )
        if draft is None:
            raise ObjectNotFound()
        return draft
