"""Content-free, append-only evidence for operational maintenance runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import Base, CreatedMixin


class OperationalRun(CreatedMixin, Base):
    __tablename__ = "operational_runs"

    job_name: Mapped[str] = mapped_column(String(80), index=True)
    policy_version: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(20))
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_counts: Mapped[dict[str, int]] = mapped_column(JSON)
