"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from istari_service.models import UserRole
from istari_service.schemas.common import ApiModel, StrictApiModel


class LoginRequest(StrictApiModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


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


class SessionResponse(ApiModel):
    user: CurrentUser
    csrf_token: str
    expires_at: datetime
    elevated_until: datetime | None


class ClientCapabilities(ApiModel):
    my_work: bool
    notifications: bool
    configuration: bool
    products: bool
    managed_file_uploads: bool
    planning: bool
    statistics: bool
