"""Bounded, idempotent reconciliation of abandoned product uploads."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mist_service.product_models import (
    ProductArtefact,
    ProductStorageQuota,
    ProductUploadIntent,
)
from mist_service.product_ports import PrivateObjectStorage
from mist_service.product_types import ArtefactLifecycle


@dataclass(frozen=True, slots=True)
class ProductCleanupReport:
    expired_intents: int
    orphan_objects: int


class ProductUploadCleanup:
    """Reconcile at most one bounded batch without trusting storage enumeration."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        storage: PrivateObjectStorage,
        *,
        batch_size: int = 100,
    ) -> None:
        if not 1 <= batch_size <= 1_000:
            raise ValueError("batch_size must be between 1 and 1000")
        self._sessions = sessions
        self._storage = storage
        self._batch_size = batch_size

    async def run(self, *, now: datetime | None = None) -> ProductCleanupReport:
        cutoff = now or datetime.now(UTC)
        self._storage.reconcile_quarantine_index(limit=self._batch_size)
        candidates = await self._expired_candidates(cutoff)
        expired = 0
        for intent_id, object_key in candidates:
            marked = False
            async with self._sessions() as session, session.begin():
                row = await session.execute(
                    select(ProductUploadIntent, ProductArtefact)
                    .join(
                        ProductArtefact,
                        ProductArtefact.id == ProductUploadIntent.artefact_id,
                    )
                    .where(ProductUploadIntent.id == intent_id)
                    .with_for_update()
                )
                intent, artefact = row.one()
                lease_active = (
                    intent.operation_lease_expires_at is not None
                    and _aware(intent.operation_lease_expires_at) > cutoff
                )
                if (
                    intent.consumed_at is None
                    and _aware(intent.expires_at) <= cutoff
                    and not lease_active
                ):
                    intent.consumed_at = cutoff
                    artefact.lifecycle = ArtefactLifecycle.EXPIRED
                    artefact.quarantine_key = None
                    artefact.version += 1
                    expired += 1
                    marked = True
            if marked:
                with contextlib.suppress(FileNotFoundError):
                    await self._storage.delete_quarantine(object_key)
        cursor = await self._cleanup_cursor()
        object_candidates = self._storage.quarantine_keys(
            limit=self._batch_size, after=cursor
        )
        if not object_candidates and cursor is not None:
            cursor = None
            object_candidates = self._storage.quarantine_keys(
                limit=self._batch_size, after=None
            )
        referenced = await self._referenced_keys(object_candidates)
        orphans = 0
        for object_key in object_candidates:
            if object_key not in referenced:
                with contextlib.suppress(FileNotFoundError):
                    await self._storage.delete_quarantine(object_key)
                orphans += 1
        await self._set_cleanup_cursor(
            object_candidates[-1] if object_candidates else cursor
        )
        return ProductCleanupReport(expired, orphans)

    async def reconcile_once(self) -> bool:
        report = await self.run()
        return bool(report.expired_intents or report.orphan_objects)

    async def _expired_candidates(self, cutoff: datetime) -> list[tuple[UUID, str]]:
        async with self._sessions() as session:
            rows = await session.execute(
                select(ProductUploadIntent.id, ProductUploadIntent.object_key)
                .where(
                    ProductUploadIntent.consumed_at.is_(None),
                    ProductUploadIntent.expires_at <= cutoff,
                    (
                        ProductUploadIntent.operation_lease_expires_at.is_(None)
                        | (ProductUploadIntent.operation_lease_expires_at <= cutoff)
                    ),
                )
                .order_by(ProductUploadIntent.expires_at, ProductUploadIntent.id)
                .limit(self._batch_size)
            )
            return list(rows.tuples())

    async def _referenced_keys(self, candidates: tuple[str, ...]) -> frozenset[str]:
        if not candidates:
            return frozenset()
        async with self._sessions() as session:
            keys = await session.scalars(
                select(ProductUploadIntent.object_key).where(
                    ProductUploadIntent.object_key.in_(candidates),
                )
            )
            return frozenset(keys)

    async def _cleanup_cursor(self) -> str | None:
        async with self._sessions() as session, session.begin():
            quota = await session.get(ProductStorageQuota, 1, with_for_update=True)
            if quota is None:
                quota = ProductStorageQuota(id=1)
                session.add(quota)
                await session.flush()
            return quota.cleanup_cursor

    async def _set_cleanup_cursor(self, value: str | None) -> None:
        async with self._sessions() as session, session.begin():
            quota = await session.get(ProductStorageQuota, 1, with_for_update=True)
            if quota is None:
                quota = ProductStorageQuota(id=1)
                session.add(quota)
            quota.cleanup_cursor = value


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
