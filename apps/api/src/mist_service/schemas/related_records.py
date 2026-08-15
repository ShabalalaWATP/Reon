"""Schemas for bounded explainable related-request matching."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, field_validator

from mist_service.models import RequestStatus
from mist_service.related_record_models import RequestLinkType
from mist_service.schemas.common import ApiModel, StrictApiModel


class RelatedRecordCandidate(ApiModel):
    id: UUID
    reference: str
    title: str
    status: RequestStatus
    required_by: date
    product_available: bool


class RelatedRecordSearchMode(StrEnum):
    HYBRID = "HYBRID"
    TEXT_ONLY = "TEXT_ONLY"


class RelatedRecordMatchMethod(StrEnum):
    FULL_TEXT = "FULL_TEXT"
    SEMANTIC = "SEMANTIC"
    STRUCTURED = "STRUCTURED"


class RelatedRecordMatchBand(StrEnum):
    STRONG = "STRONG"
    POSSIBLE = "POSSIBLE"
    LIMITED = "LIMITED"


class RelatedRecordEvidence(ApiModel):
    field: str
    reason: str
    excerpt: str


class RelatedRecordMatch(RelatedRecordCandidate):
    match_strength: int = Field(ge=0, le=100)
    match_band: RelatedRecordMatchBand
    methods: list[RelatedRecordMatchMethod]
    reasons: list[str]
    evidence: list[RelatedRecordEvidence]


class RelatedRecordCandidateList(ApiModel):
    mode: RelatedRecordSearchMode
    items: list[RelatedRecordMatch]


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
