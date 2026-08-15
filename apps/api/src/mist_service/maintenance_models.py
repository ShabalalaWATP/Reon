"""Durable leases and health for independently deployed worker jobs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.models import UTC_TS, Base


class MaintenanceJobState(Base):
    __tablename__ = "maintenance_job_states"
    __table_args__ = (
        CheckConstraint("lease_generation >= 0", name="lease_generation_nonnegative"),
    )

    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64))
    lease_generation: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTC_TS, index=True)
    last_started_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    last_success_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    last_failure_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
