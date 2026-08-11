"""Reusable persistence fields for bounded personal profile data."""

from __future__ import annotations

from sqlalchemy import JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column


class ProfileFieldsMixin:
    """Personal attributes shared by the user aggregate and profile adapter."""

    profile_team: Mapped[str | None] = mapped_column(String(120))
    rank_or_grade: Mapped[str | None] = mapped_column(String(120))
    service_number: Mapped[str | None] = mapped_column(String(80))
    additional_information: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'")
    )
