"""Durable platform marking and content-minimised access-assistance attempts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.models import (
    UTC_TS,
    UUID_TYPE,
    Base,
    CreatedMixin,
    TimestampMixin,
)
from mist_service.platform_security_types import PlatformClassification

PLATFORM_CLASSIFICATION_ID = UUID("00000000-0000-0000-0000-000000000002")


class PlatformClassificationSetting(TimestampMixin, Base):
    __tablename__ = "platform_classification_settings"
    __table_args__ = (
        CheckConstraint("version > 0", name="platform_classification_version"),
    )

    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True)
    classification: Mapped[PlatformClassification] = mapped_column(
        SqlEnum(
            PlatformClassification,
            name="platform_classification",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda members: [member.value for member in members],
        )
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class PasswordAssistanceAttempt(CreatedMixin, Base):
    __tablename__ = "password_assistance_attempts"
    __table_args__ = (
        Index(
            "ix_password_assistance_source_created",
            "source_key",
            "created_at",
        ),
        Index(
            "ix_password_assistance_user_created",
            "matched_user_id",
            "created_at",
        ),
    )

    source_key: Mapped[str] = mapped_column(String(72))
    matched_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    email_key_id: Mapped[str | None] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(
        String(16), default="PENDING", server_default="PENDING", index=True
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTC_TS, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
