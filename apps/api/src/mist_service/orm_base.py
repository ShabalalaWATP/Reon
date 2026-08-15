"""Neutral SQLAlchemy base, column types and model mixins."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


UTC_TS = DateTime(timezone=True)
UUID_TYPE = Uuid(as_uuid=True)


class IdMixin:
    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid4)


class CreatedMixin(IdMixin):
    created_at: Mapped[datetime] = mapped_column(UTC_TS, server_default=func.now())


class TimestampMixin(CreatedMixin):
    updated_at: Mapped[datetime] = mapped_column(
        UTC_TS, server_default=func.now(), onupdate=func.now()
    )


def _enum(enum_type: type[StrEnum], name: str) -> SqlEnum:
    return SqlEnum(enum_type, name=name, native_enum=False, create_constraint=True)
