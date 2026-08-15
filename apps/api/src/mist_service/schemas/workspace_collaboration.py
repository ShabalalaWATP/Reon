"""Validated contracts for bounded workspace collaboration records."""

from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from mist_service.schemas.common import ApiModel, StrictApiModel
from mist_service.workspace_collaboration_models import (
    WorkspaceRecordKind,
    WorkspaceRecordStatus,
)


class WorkspaceRecordCreate(StrictApiModel):
    grant_id: UUID
    kind: WorkspaceRecordKind
    title: Annotated[str, Field(min_length=3, max_length=160)]
    body: Annotated[str, Field(min_length=3, max_length=4000)]
    url: Annotated[str, Field(max_length=500)] | None = None

    @field_validator("title", "body")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def valid_link(self) -> WorkspaceRecordCreate:
        if self.kind is WorkspaceRecordKind.LINK and self.url is None:
            raise ValueError("A useful link requires an HTTPS URL.")
        if self.url is not None:
            self.url = canonical_workspace_url(self.url)
        return self


def canonical_workspace_url(value: str) -> str:
    """Canonicalise a public HTTPS destination and reject parser confusion."""

    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Workspace links cannot contain control characters.")
    if "\\" in value:
        raise ValueError("Workspace links cannot contain backslashes.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("Workspace links must use a normal HTTPS URL.") from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in {None, 443}
    ):
        raise ValueError("Workspace links must use a normal HTTPS URL.")
    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname or "%" in hostname:
        raise ValueError("Workspace links must use a public HTTPS destination.")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Workspace links contain an invalid hostname.") from error
    if _is_private_destination(hostname):
        raise ValueError("Workspace links must use a public HTTPS destination.")
    host = f"[{hostname}]" if ":" in hostname else hostname
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def _is_private_destination(hostname: str) -> bool:
    try:
        destination = ip_address(hostname)
    except ValueError:
        return hostname == "localhost" or hostname.endswith(
            (".localhost", ".local", ".internal")
        )
    return not destination.is_global


class WorkspaceRecordResolve(StrictApiModel):
    grant_id: UUID
    expected_version: Annotated[int, Field(ge=1)]
    resolution: Annotated[str, Field(min_length=10, max_length=1000)]


class WorkspaceRecordView(ApiModel):
    id: UUID
    kind: WorkspaceRecordKind
    status: WorkspaceRecordStatus
    title: str
    body: str
    url: str | None
    created_by_display_name: str
    resolution: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class WorkspaceRecordList(ApiModel):
    items: list[WorkspaceRecordView]
