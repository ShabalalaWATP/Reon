"""Content-free distributed login rate-limit state."""

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from istari_service.models import UTC_TS, Base


class LoginRateLimit(Base):
    __tablename__ = "login_rate_limits"
    __table_args__ = (
        CheckConstraint(
            "attempt_count > 0",
            name="login_rate_limit_attempt_count_positive",
        ),
        Index("ix_login_rate_limits_expires_at", "expires_at"),
    )

    scope_key: Mapped[str] = mapped_column(String(72), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(UTC_TS)
    attempt_count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(UTC_TS)
