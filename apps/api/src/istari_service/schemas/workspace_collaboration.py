"""Validated contracts for bounded workspace collaboration records."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from istari_service.schemas.common import ApiModel, StrictApiModel
from istari_service.workspace_collaboration_models import (
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
            parsed = urlparse(self.url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username:
                raise ValueError("Workspace links must use a normal HTTPS URL.")
        return self


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
