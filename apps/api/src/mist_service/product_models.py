"""Private managed-product metadata owned by PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from mist_service.orm_base import (
    UTC_TS,
    UUID_TYPE,
    Base,
    CreatedMixin,
    TimestampMixin,
    _enum,
)
from mist_service.product_types import (
    AccessKind,
    AccessOutcome,
    ArtefactKind,
    ArtefactLifecycle,
    PackageStatus,
    ScanResult,
)


class ProductPackage(TimestampMixin, Base):
    __tablename__ = "product_packages"
    __table_args__ = (
        UniqueConstraint("request_id", "package_version"),
        UniqueConstraint("creation_key"),
        CheckConstraint("package_version > 0", name="product_package_version"),
        CheckConstraint("version > 0", name="product_package_record_version"),
        CheckConstraint(
            "policy_version IN (1, 2)", name="product_package_policy_version"
        ),
    )

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), index=True
    )
    package_version: Mapped[int] = mapped_column(Integer)
    creation_key: Mapped[UUID] = mapped_column(UUID_TYPE)
    author_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[PackageStatus] = mapped_column(
        _enum(PackageStatus, "product_package_status"), index=True
    )
    covering_note: Mapped[str | None] = mapped_column(Text)
    policy_version: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    package_checksum: Mapped[str | None] = mapped_column(String(64))
    manager_approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    manager_approved_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    disseminated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    disseminated_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    withdrawn_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    withdrawal_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ProductStorageQuota(Base):
    """Singleton row serialising global storage reservations."""

    __tablename__ = "product_storage_quotas"
    __table_args__ = (
        CheckConstraint("id = 1", name="product_storage_quota_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cleanup_cursor: Mapped[str | None] = mapped_column(String(255))


class ProductArtefact(TimestampMixin, Base):
    __tablename__ = "product_artefacts"
    __table_args__ = (
        UniqueConstraint("package_id", "position"),
        UniqueConstraint("creation_key"),
        CheckConstraint("position BETWEEN 1 AND 10", name="product_artefact_position"),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0", name="product_artefact_size"
        ),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_packages.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    creation_key: Mapped[UUID] = mapped_column(UUID_TYPE)
    kind: Mapped[ArtefactKind] = mapped_column(
        _enum(ArtefactKind, "product_artefact_kind")
    )
    lifecycle: Mapped[ArtefactLifecycle] = mapped_column(
        _enum(ArtefactLifecycle, "product_artefact_lifecycle"), index=True
    )
    label: Mapped[str] = mapped_column(String(160))
    filename: Mapped[str | None] = mapped_column(String(180))
    media_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    quarantine_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    released_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ProductUploadIntent(CreatedMixin, Base):
    __tablename__ = "product_upload_intents"
    __table_args__ = (
        UniqueConstraint("artefact_id", "idempotency_key"),
        UniqueConstraint("object_key"),
        CheckConstraint(
            "operation_lease_generation >= 0",
            name="lease_generation_nonnegative",
        ),
        Index(
            "ix_product_upload_intents_operation_lease",
            "operation_lease_expires_at",
            "id",
        ),
    )

    artefact_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_artefacts.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE)
    object_key: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expected_size_bytes: Mapped[int] = mapped_column(Integer)
    expected_media_type: Mapped[str] = mapped_column(String(120))
    expected_checksum: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    consumed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    operation_lease_owner: Mapped[str | None] = mapped_column(String(64))
    operation_lease_generation: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    operation_lease_expires_at: Mapped[datetime | None] = mapped_column(UTC_TS)


class ProductScan(CreatedMixin, Base):
    __tablename__ = "product_scans"
    __table_args__ = (UniqueConstraint("artefact_id", "idempotency_key"),)

    artefact_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_artefacts.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE)
    result: Mapped[ScanResult] = mapped_column(
        _enum(ScanResult, "product_scan_result"), index=True
    )
    scanner: Mapped[str] = mapped_column(String(80))
    scanner_version: Mapped[str] = mapped_column(String(40))
    checksum: Mapped[str] = mapped_column(String(64))
    reason_code: Mapped[str | None] = mapped_column(String(80))
    findings: Mapped[list[str]] = mapped_column(JSON, default=list)


class ExternalProductLink(CreatedMixin, Base):
    __tablename__ = "external_product_links"

    artefact_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_artefacts.id", ondelete="RESTRICT"), unique=True
    )
    destination_url: Mapped[str] = mapped_column(Text)
    normalised_domain: Mapped[str] = mapped_column(String(253), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    qc_attested: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class ProductDissemination(CreatedMixin, Base):
    __tablename__ = "product_disseminations"
    __table_args__ = (
        UniqueConstraint("package_id", "recipient_user_id"),
        UniqueConstraint("idempotency_key"),
    )

    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_packages.id", ondelete="RESTRICT"), index=True
    )
    recipient_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    disseminated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[UUID] = mapped_column(UUID_TYPE)
    package_checksum: Mapped[str] = mapped_column(String(64))
    withdrawn_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    accepted_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    acceptance_key: Mapped[UUID | None] = mapped_column(UUID_TYPE, unique=True)


class ProductAccessEvent(CreatedMixin, Base):
    __tablename__ = "product_access_events"
    __table_args__ = (
        Index("ix_product_access_events_artefact_created", "artefact_id", "created_at"),
    )

    request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT"), index=True
    )
    package_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_packages.id", ondelete="RESTRICT"), index=True
    )
    artefact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_artefacts.id", ondelete="RESTRICT"), index=True
    )
    target_hash: Mapped[str] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[AccessKind] = mapped_column(_enum(AccessKind, "product_access_kind"))
    outcome: Mapped[AccessOutcome] = mapped_column(
        _enum(AccessOutcome, "product_access_outcome"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(80))
    correlation_id: Mapped[str | None] = mapped_column(String(80))


def _reject_mutation(_mapper: Any, _connection: Any, _target: Any) -> None:
    raise ValueError("product audit records are append-only")


event.listen(ProductAccessEvent, "before_update", _reject_mutation)
event.listen(ProductAccessEvent, "before_delete", _reject_mutation)
