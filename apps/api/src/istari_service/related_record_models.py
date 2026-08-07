"""Append-only human judgements linking authorised service requests."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UUID_TYPE, Base, CreatedMixin, _enum


class RequestLinkType(StrEnum):
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    RELATED_REQUEST = "RELATED_REQUEST"
    EXISTING_OUTPUT = "EXISTING_OUTPUT"


class RequestLink(CreatedMixin, Base):
    __tablename__ = "request_links"
    __table_args__ = (
        CheckConstraint(
            "source_request_id <> target_request_id", name="different_request"
        ),
        UniqueConstraint(
            "source_request_id",
            "target_request_id",
            "link_type",
            name="uq_request_links_source_target_type",
        ),
    )

    source_request_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("service_requests.id", ondelete="RESTRICT"),
        index=True,
    )
    target_request_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("service_requests.id", ondelete="RESTRICT"),
        index=True,
    )
    link_type: Mapped[RequestLinkType] = mapped_column(
        _enum(RequestLinkType, "request_link_type"),
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        UUID_TYPE,
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    actor_display_name: Mapped[str] = mapped_column(String(120))
