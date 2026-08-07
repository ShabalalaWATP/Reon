"""Schemas for bounded manual related-record checks."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.models import RequestStatus
from istari_service.related_record_models import RequestLinkType
from istari_service.schemas.common import ApiModel, StrictApiModel


class RelatedRecordCandidate(ApiModel):
    id: UUID
    reference: str
    title: str
    status: RequestStatus
    required_by: date
    product_available: bool


class RelatedRecordCandidateList(ApiModel):
    items: list[RelatedRecordCandidate]


class RequestLinkCreate(StrictApiModel):
    expected_version: int = Field(ge=1)
    target_request_id: UUID
    link_type: RequestLinkType
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reason_is_meaningful(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("reason must contain at least 10 non-space characters")
        return cleaned


class RequestLinkView(ApiModel):
    id: UUID
    target: RelatedRecordCandidate
    link_type: RequestLinkType
    reason: str
    actor_display_name: str
    created_at: datetime


class RequestLinkWorkspace(ApiModel):
    source_version: int
    items: list[RequestLinkView]
