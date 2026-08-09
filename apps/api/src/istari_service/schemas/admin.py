"""Strict camel-case contracts for bounded platform administration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.models import UserRole
from istari_service.organisation_models import OrganisationKind
from istari_service.schemas.common import ApiModel, StrictApiModel


class AdminMembership(ApiModel):
    organisation_unit_id: UUID
    organisation_unit_name: str
    organisation_unit_kind: OrganisationKind


class AdminUser(ApiModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole
    scope: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    memberships: list[AdminMembership]


class AdminUserList(ApiModel):
    items: list[AdminUser]
    next_cursor: str | None = None


class AdminUserCreate(StrictApiModel):
    display_name: str = Field(min_length=2, max_length=120)
    role: UserRole
    scope: str = Field(min_length=1, max_length=120)
    organisation_unit_ids: list[UUID] = Field(default_factory=list, max_length=40)

    @field_validator("organisation_unit_ids")
    @classmethod
    def unique_units(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("organisation memberships must be unique")
        return value


class AdminUserPatch(AdminUserCreate):
    expected_version: int = Field(ge=1)


class AdminStatusPatch(StrictApiModel):
    is_active: bool
    expected_version: int = Field(ge=1)


class AdminOrganisationRename(StrictApiModel):
    name: str = Field(min_length=2, max_length=120)
    expected_version: int = Field(ge=1)
