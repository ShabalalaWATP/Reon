"""Initial route creation kept separate from route progression queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.organisation_models import (
    OrganisationKind,
    OrganisationUnit,
    RequestRouteSelection,
)


async def initialise_request_route(
    session: AsyncSession, request_id: UUID, *, root_id: UUID | None = None
) -> None:
    selected_root = root_id or await session.scalar(
        select(OrganisationUnit.id).where(
            OrganisationUnit.kind == OrganisationKind.ROOT,
            OrganisationUnit.is_configured.is_(True),
        )
    )
    if selected_root is None:
        raise RuntimeError("the organisation root is not configured")
    session.add(
        RequestRouteSelection(request_id=request_id, unit_id=selected_root, position=0)
    )
