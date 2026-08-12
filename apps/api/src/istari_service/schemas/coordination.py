"""Commands for non-blocking, request-scoped coordination."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.schemas.common import ApiModel
from istari_service.schemas.organisation import TrackedRequestEvent


class CoordinationAudience(StrEnum):
    CUSTOMER = "CUSTOMER"
    CURRENT_OWNER = "CURRENT_OWNER"


class CoordinationMessageCreate(ApiModel):
    audience: CoordinationAudience
    body: Annotated[str, Field(min_length=3, max_length=2_000)]

    @field_validator("body")
    @classmethod
    def normalise_body(cls, value: str) -> str:
        return " ".join(value.split())


class ReturnRequestCreate(ApiModel):
    target_unit_id: UUID
    reason: Annotated[str, Field(min_length=10, max_length=2_000)]

    @field_validator("reason")
    @classmethod
    def normalise_reason(cls, value: str) -> str:
        return " ".join(value.split())


class CoordinationResult(ApiModel):
    event: TrackedRequestEvent
