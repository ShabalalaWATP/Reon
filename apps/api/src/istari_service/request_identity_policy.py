"""Stable-identity separation between Customers and staff production work."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID


def require_requester_excluded(
    requester_id: UUID | None,
    participant_ids: Iterable[UUID],
    error: Exception,
) -> None:
    """Deny missing requests and any production participation by the requester."""

    if requester_id is None or requester_id in set(participant_ids):
        raise error
