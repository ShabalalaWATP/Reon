"""Neutral application records for explainable related-request decisions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RelatedRecordSource:
    """Authorised source request and optimistic-lock version."""

    request_id: UUID
    version: int
