"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from mist_service.identity_validation import normalise_email
from mist_service.models import IdentityContext, UserRole
from mist_service.schemas.common import ApiModel, StrictApiModel


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


class SwitchContextRequest(StrictApiModel):
    context: IdentityContext


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
    active_context: IdentityContext
    available_contexts: list[IdentityContext]
    context_version: int


class ClientCapabilities(ApiModel):
    """Release capabilities advertised to tolerant clients.

    Additive capabilities default closed so older or partially composed servers
    cannot accidentally enable a new client command surface.
    """

    my_work: bool
    notifications: bool
    configuration: bool
    products: bool
    managed_file_uploads: bool
    planning: bool
    statistics: bool
    conversation_reads: bool = False
    conversation_writes: bool = False
    context_switching: bool = False
