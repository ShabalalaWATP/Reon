"""Retire legacy image artefacts created outside their pinned policy.

Revision ID: 0049_legacy_product_cleanup
Revises: 0048_notification_position
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_legacy_product_cleanup"
down_revision: str | None = "0048_notification_position"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

packages = sa.table(
    "product_packages",
    sa.column("id"),
    sa.column("policy_version"),
    sa.column("status"),
    sa.column("withdrawn_at"),
    sa.column("withdrawal_reason"),
    sa.column("version"),
)
artefacts = sa.table(
    "product_artefacts",
    sa.column("id"),
    sa.column("package_id"),
    sa.column("kind"),
    sa.column("media_type"),
    sa.column("lifecycle"),
    sa.column("version"),
)
upload_intents = sa.table(
    "product_upload_intents",
    sa.column("artefact_id"),
    sa.column("consumed_at"),
    sa.column("expires_at"),
    sa.column("operation_lease_owner"),
    sa.column("operation_lease_expires_at"),
)
disseminations = sa.table(
    "product_disseminations",
    sa.column("package_id"),
    sa.column("withdrawn_at"),
)


def _invalid_artefact_filter() -> sa.ColumnElement[bool]:
    return sa.and_(
        packages.c.policy_version == 1,
        artefacts.c.kind == "MANAGED_FILE",
        artefacts.c.media_type.in_(("image/jpeg", "image/png")),
        artefacts.c.lifecycle.not_in(("WITHDRAWN", "REPLACED")),
    )


def _invalid_artefact_ids() -> sa.Select[tuple[object]]:
    return (
        sa.select(artefacts.c.id)
        .join(packages, packages.c.id == artefacts.c.package_id)
        .where(_invalid_artefact_filter())
    )


def _invalid_package_ids() -> sa.Select[tuple[object]]:
    return (
        sa.select(artefacts.c.package_id)
        .join(packages, packages.c.id == artefacts.c.package_id)
        .where(_invalid_artefact_filter())
        .distinct()
    )


def upgrade() -> None:
    now = sa.func.current_timestamp()
    op.execute(
        sa.update(upload_intents)
        .where(upload_intents.c.artefact_id.in_(_invalid_artefact_ids()))
        .values(
            consumed_at=sa.func.coalesce(upload_intents.c.consumed_at, now),
            expires_at=now,
            operation_lease_owner=None,
            operation_lease_expires_at=None,
        )
    )
    op.execute(
        sa.update(disseminations)
        .where(disseminations.c.package_id.in_(_invalid_package_ids()))
        .values(
            withdrawn_at=sa.func.coalesce(disseminations.c.withdrawn_at, now),
        )
    )
    op.execute(
        sa.update(packages)
        .where(
            packages.c.id.in_(_invalid_package_ids()),
            packages.c.status.not_in(("WITHDRAWN", "REPLACED")),
        )
        .values(
            status="WITHDRAWN",
            withdrawn_at=sa.func.coalesce(packages.c.withdrawn_at, now),
            withdrawal_reason=sa.func.coalesce(
                packages.c.withdrawal_reason,
                "Retired because an artefact breached the pinned package policy.",
            ),
            version=packages.c.version + 1,
        )
    )
    op.execute(
        sa.update(artefacts)
        .where(
            artefacts.c.id.in_(_invalid_artefact_ids()),
            artefacts.c.lifecycle.not_in(("WITHDRAWN", "REPLACED")),
        )
        .values(
            lifecycle="WITHDRAWN",
            version=artefacts.c.version + 1,
        )
    )


def downgrade() -> None:
    # Security retirement is intentionally irreversible: restoring an artefact
    # that violated its immutable policy would recreate the vulnerability.
    pass
