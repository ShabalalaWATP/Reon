"""Signed-in self-profile contracts."""

from __future__ import annotations

import unicodedata
from uuid import UUID

from pydantic import Field, field_validator

from istari_service.models import UserRole
from istari_service.schemas.common import ApiModel, StrictApiModel


def _plain_optional(value: str | None, *, maximum: int) -> str | None:
    if value is None:
        return None
    cleaned = unicodedata.normalize("NFKC", value).strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise ValueError(f"value must not exceed {maximum} characters")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in cleaned):
        raise ValueError("value cannot contain control or bidirectional characters")
    return cleaned


class ProfileView(ApiModel):
    user_id: UUID
    name: str
    username: str
    email: str
    role: UserRole
    profile_team: str | None
    rank_or_grade: str | None
    service_number: str | None
    additional_information: str | None
    skills: list[str]
    version: int


class ProfileUpdate(StrictApiModel):
    profile_team: str | None = Field(default=None, max_length=120)
    rank_or_grade: str | None = Field(default=None, max_length=120)
    service_number: str | None = Field(default=None, max_length=80)
    additional_information: str | None = Field(default=None, max_length=2000)
    skills: list[str] = Field(default_factory=list, max_length=12)
    expected_version: int = Field(ge=1)

    @field_validator("profile_team", "rank_or_grade")
    @classmethod
    def bounded_labels(cls, value: str | None) -> str | None:
        return _plain_optional(value, maximum=120)

    @field_validator("service_number")
    @classmethod
    def bounded_service_number(cls, value: str | None) -> str | None:
        return _plain_optional(value, maximum=80)

    @field_validator("additional_information")
    @classmethod
    def bounded_information(cls, value: str | None) -> str | None:
        return _plain_optional(value, maximum=2000)

    @field_validator("skills")
    @classmethod
    def bounded_skills(cls, value: list[str]) -> list[str]:
        cleaned = [_plain_optional(item, maximum=80) for item in value]
        labels = [item for item in cleaned if item is not None]
        if len({item.casefold() for item in labels}) != len(labels):
            raise ValueError("skills must be unique")
        return labels
