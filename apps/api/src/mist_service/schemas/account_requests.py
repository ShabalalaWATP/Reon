"""Public submission and administrator review contracts for account requests."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from mist_service.account_request_models import AccountRequestStatus
from mist_service.identity_validation import normalise_email
from mist_service.schemas.common import ApiModel, StrictApiModel


class AccountRequestCreate(StrictApiModel):
    display_name: str = Field(min_length=2, max_length=120)
    contact_email: str = Field(min_length=3, max_length=254)
    reason: str = Field(min_length=10, max_length=1000)

    @field_validator("display_name", "reason")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value: str) -> str:
        return normalise_email(value)


class AccountRequestAccepted(ApiModel):
    status: str = "pending"


class AccountRequestView(ApiModel):
    id: UUID
    display_name: str
    contact_email: str
    reason: str
    status: AccountRequestStatus
    decision_note: str | None
    created_user_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


class AccountRequestList(ApiModel):
    items: list[AccountRequestView]


class AccountRequestApprove(StrictApiModel):
    expected_version: int = Field(ge=1)


class AccountRequestReject(AccountRequestApprove):
    decision_note: str = Field(min_length=3, max_length=1000)
