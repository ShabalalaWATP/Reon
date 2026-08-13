"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.identity_validation import normalise_email
from istari_service.models import UserRole
from istari_service.schemas.common import ApiModel, StrictApiModel


class LoginRequest(StrictApiModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class PasswordAssistanceRequest(StrictApiModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalise_email(value)


class PasswordAssistanceAccepted(ApiModel):
    status: str = "accepted"
    message: str = (
        "If an active account matches that email, an administrator has been notified."
    )


class PasswordConfirmation(StrictApiModel):
    password: str = Field(min_length=1, max_length=1024)


class ElevationResponse(ApiModel):
    elevated_until: datetime


class CurrentUser(ApiModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole
    scope: str
    organisation_unit_ids: list[UUID] = Field(default_factory=list)


class SessionResponse(ApiModel):
    user: CurrentUser
    csrf_token: str
    expires_at: datetime
    idle_expires_at: datetime
    idle_timeout_seconds: int
    elevated_until: datetime | None


class ClientCapabilities(ApiModel):
    my_work: bool
    notifications: bool
    configuration: bool
    products: bool
    managed_file_uploads: bool
    planning: bool
    statistics: bool
