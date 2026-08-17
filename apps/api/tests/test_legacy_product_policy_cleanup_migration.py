"""Regression coverage for retiring artefacts outside their pinned policy."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa


def _migration() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0049_legacy_product_policy_cleanup.py"
    )
    specification = spec_from_file_location("legacy_product_policy_cleanup", path)
    assert specification is not None and specification.loader is not None
    migration = module_from_spec(specification)
    specification.loader.exec_module(migration)
    return migration


def _create_tables(connection: sa.Connection) -> None:
    for statement in (
        """CREATE TABLE product_packages (
            id TEXT PRIMARY KEY, policy_version INTEGER, status TEXT,
            withdrawn_at TIMESTAMP, withdrawal_reason TEXT, version INTEGER
        )""",
        """CREATE TABLE product_artefacts (
            id TEXT PRIMARY KEY, package_id TEXT, kind TEXT, media_type TEXT,
            lifecycle TEXT, version INTEGER
        )""",
        """CREATE TABLE product_upload_intents (
            artefact_id TEXT, consumed_at TIMESTAMP, expires_at TIMESTAMP,
            operation_lease_owner TEXT, operation_lease_expires_at TIMESTAMP
        )""",
        """CREATE TABLE product_disseminations (
            package_id TEXT, withdrawn_at TIMESTAMP
        )""",
    ):
        connection.execute(sa.text(statement))


def _seed_case(
    connection: sa.Connection,
    *,
    suffix: str,
    policy_version: int,
    media_type: str,
    lifecycle: str = "CURRENT",
) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO product_packages VALUES "
            "(:package_id, :policy_version, 'APPROVED', NULL, NULL, 1)"
        ),
        {"package_id": f"package-{suffix}", "policy_version": policy_version},
    )
    connection.execute(
        sa.text(
            "INSERT INTO product_artefacts VALUES "
            "(:artefact_id, :package_id, 'MANAGED_FILE', :media_type, "
            ":lifecycle, 1)"
        ),
        {
            "artefact_id": f"artefact-{suffix}",
            "package_id": f"package-{suffix}",
            "media_type": media_type,
            "lifecycle": lifecycle,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO product_upload_intents VALUES "
            "(:artefact_id, NULL, '2099-01-01', 'worker', '2099-01-01')"
        ),
        {"artefact_id": f"artefact-{suffix}"},
    )
    connection.execute(
        sa.text("INSERT INTO product_disseminations VALUES (:package_id, NULL)"),
        {"package_id": f"package-{suffix}"},
    )


def test_upgrade_retires_only_active_legacy_images(monkeypatch) -> None:
    migration = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _create_tables(connection)
        _seed_case(
            connection, suffix="legacy-image", policy_version=1, media_type="image/png"
        )
        _seed_case(
            connection,
            suffix="legacy-pdf",
            policy_version=1,
            media_type="application/pdf",
        )
        _seed_case(
            connection,
            suffix="current-image",
            policy_version=2,
            media_type="image/jpeg",
        )
        _seed_case(
            connection,
            suffix="replaced-image",
            policy_version=1,
            media_type="image/png",
            lifecycle="REPLACED",
        )
        monkeypatch.setattr(migration.op, "execute", connection.execute)

        migration.upgrade()

        packages = dict(
            connection.execute(
                sa.text("SELECT id, status FROM product_packages ORDER BY id")
            ).all()
        )
        artefacts = dict(
            connection.execute(
                sa.text("SELECT id, lifecycle FROM product_artefacts ORDER BY id")
            ).all()
        )
        intent = connection.execute(
            sa.text(
                "SELECT consumed_at, operation_lease_owner "
                "FROM product_upload_intents "
                "WHERE artefact_id = 'artefact-legacy-image'"
            )
        ).one()
        dissemination = connection.execute(
            sa.text(
                "SELECT withdrawn_at FROM product_disseminations "
                "WHERE package_id = 'package-legacy-image'"
            )
        ).scalar_one()

    monkeypatch.undo()
    engine.dispose()

    assert packages == {
        "package-current-image": "APPROVED",
        "package-legacy-image": "WITHDRAWN",
        "package-legacy-pdf": "APPROVED",
        "package-replaced-image": "APPROVED",
    }
    assert artefacts == {
        "artefact-current-image": "CURRENT",
        "artefact-legacy-image": "WITHDRAWN",
        "artefact-legacy-pdf": "CURRENT",
        "artefact-replaced-image": "REPLACED",
    }
    assert intent[0] is not None and intent[1] is None
    assert dissemination is not None
