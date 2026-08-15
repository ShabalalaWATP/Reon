"""Stable requester exclusion for mutations of linked board packages."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from mist_service.board_ports import WorkPackageRecord
from mist_service.errors import BoardItemNotFound
from mist_service.request_identity_policy import require_requester_excluded


class BoardRequestIdentityReader(Protocol):
    async def request_requester_id(self, request_id: UUID) -> UUID | None: ...

    async def package_contributor_ids(self, package_id: UUID) -> set[UUID]: ...


async def require_package_requester_excluded(
    board: BoardRequestIdentityReader,
    package: WorkPackageRecord,
    actor_id: UUID,
    additional_ids: Iterable[UUID] = (),
) -> None:
    if package.linked_request_id is None:
        return
    requester_id = await board.request_requester_id(package.linked_request_id)
    contributors = await board.package_contributor_ids(package.id)
    require_requester_excluded(
        requester_id,
        {actor_id, package.owner_user_id, *contributors, *additional_ids},
        BoardItemNotFound(),
    )
