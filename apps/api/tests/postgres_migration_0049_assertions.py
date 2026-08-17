"""PostgreSQL assurance for legacy product-policy clean-up."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from postgres_migration_probe import REVISION_0048, REVISION_0049, assert_revision, rows
from postgres_migration_seed import (
    PACKAGE_ID,
    REQUESTER_ID,
    SECOND_PACKAGE_ID,
    STAFF_ID,
)

INVALID_ARTEFACT_ID = UUID("41000000-0000-0000-0000-000000000001")
VALID_PDF_ID = UUID("41000000-0000-0000-0000-000000000002")
CURRENT_IMAGE_ID = UUID("41000000-0000-0000-0000-000000000003")
REPLACED_IMAGE_ID = UUID("41000000-0000-0000-0000-000000000004")


async def seed_0049_legacy_products(connection: AsyncConnection) -> None:
    artefacts = (
        (INVALID_ARTEFACT_ID, PACKAGE_ID, 1, "image/png", "CLEAN"),
        (VALID_PDF_ID, PACKAGE_ID, 2, "application/pdf", "CLEAN"),
        (REPLACED_IMAGE_ID, PACKAGE_ID, 3, "image/jpeg", "REPLACED"),
        (CURRENT_IMAGE_ID, SECOND_PACKAGE_ID, 1, "image/jpeg", "CLEAN"),
    )
    for artefact_id, package_id, position, media_type, lifecycle in artefacts:
        await connection.execute(
            text(
                "INSERT INTO product_artefacts "
                "(id, package_id, position, creation_key, kind, lifecycle, label, "
                "filename, media_type, size_bytes, checksum) VALUES "
                "(:id, :package, :position, :creation_key, 'MANAGED_FILE', "
                ":lifecycle, 'Synthetic migration artefact', 'synthetic.bin', "
                ":media_type, 16, :checksum)"
            ),
            {
                "id": artefact_id,
                "package": package_id,
                "position": position,
                "creation_key": UUID(int=artefact_id.int + 16),
                "lifecycle": lifecycle,
                "media_type": media_type,
                "checksum": f"{position}" * 64,
            },
        )
    await connection.execute(
        text(
            "INSERT INTO product_upload_intents "
            "(id, artefact_id, idempotency_key, object_key, token_hash, "
            "expected_size_bytes, expected_media_type, expected_checksum, "
            "expires_at, operation_lease_owner, operation_lease_expires_at) VALUES "
            "(:id, :artefact, :key, 'migration/object', :token, 16, 'image/png', "
            ":checksum, now() + INTERVAL '1 day', 'migration-worker', "
            "now() + INTERVAL '1 day')"
        ),
        {
            "id": UUID("42000000-0000-0000-0000-000000000001"),
            "artefact": INVALID_ARTEFACT_ID,
            "key": UUID("42000000-0000-0000-0000-000000000002"),
            "token": "a" * 64,
            "checksum": "1" * 64,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO product_disseminations "
            "(id, package_id, recipient_user_id, disseminated_by_user_id, "
            "idempotency_key, package_checksum) VALUES "
            "(:id, :package, :recipient, :staff, :key, :checksum)"
        ),
        {
            "id": UUID("43000000-0000-0000-0000-000000000001"),
            "package": PACKAGE_ID,
            "recipient": REQUESTER_ID,
            "staff": STAFF_ID,
            "key": UUID("43000000-0000-0000-0000-000000000002"),
            "checksum": "f" * 64,
        },
    )


async def assert_0049(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0049)
    packages = dict(
        await rows(
            connection,
            "SELECT id::text, status FROM product_packages "
            "WHERE id IN (:legacy, :current) ORDER BY id",
            {"legacy": PACKAGE_ID, "current": SECOND_PACKAGE_ID},
        )
    )
    assert packages == {str(PACKAGE_ID): "WITHDRAWN", str(SECOND_PACKAGE_ID): "DRAFT"}
    artefacts = dict(
        await rows(
            connection,
            "SELECT id::text, lifecycle FROM product_artefacts ORDER BY id",
        )
    )
    assert artefacts == {
        str(INVALID_ARTEFACT_ID): "WITHDRAWN",
        str(VALID_PDF_ID): "CLEAN",
        str(CURRENT_IMAGE_ID): "CLEAN",
        str(REPLACED_IMAGE_ID): "REPLACED",
    }
    assert await rows(
        connection,
        "SELECT consumed_at IS NOT NULL, operation_lease_owner IS NULL "
        "FROM product_upload_intents WHERE artefact_id=:artefact",
        {"artefact": INVALID_ARTEFACT_ID},
    ) == [(True, True)]
    assert await rows(
        connection,
        "SELECT withdrawn_at IS NOT NULL FROM product_disseminations "
        "WHERE package_id=:package",
        {"package": PACKAGE_ID},
    ) == [(True,)]


async def assert_0049_downgrade(connection: AsyncConnection) -> None:
    await assert_revision(connection, REVISION_0048)
    assert await rows(
        connection,
        "SELECT status FROM product_packages WHERE id=:package",
        {"package": PACKAGE_ID},
    ) == [("WITHDRAWN",)]
