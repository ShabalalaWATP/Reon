"""Neutral application records shared by work use cases and adapters."""

from __future__ import annotations

from dataclasses import dataclass

from istari_service.domain import WorkRecord
from istari_service.schemas.work import WorkItem


@dataclass(frozen=True, slots=True)
class WorkBundle:
    """Authorisation record paired with its API-facing work-item view."""

    record: WorkRecord
    view: WorkItem
