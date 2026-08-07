"""Stable delivery-team assignment identity.

Revision ID: 0016_stable_team
Revises: 0015_planning_analytics
Create Date: 2026-08-07 23:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_stable_team"
down_revision: str | None = "0015_planning_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("service_requests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("assigned_delivery_team_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            op.f("fk_service_requests_assigned_delivery_team_id_organisation_units"),
            "organisation_units",
            ["assigned_delivery_team_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_service_requests_assigned_delivery_team_id"),
            ["assigned_delivery_team_id"],
            unique=False,
        )
    _backfill_team_ids()


def _backfill_team_ids() -> None:
    requests = sa.table(
        "service_requests",
        sa.column("id", sa.Uuid()),
        sa.column("assigned_delivery_team_id", sa.Uuid()),
    )
    routes = sa.table(
        "request_route_selections",
        sa.column("request_id", sa.Uuid()),
        sa.column("unit_id", sa.Uuid()),
        sa.column("position", sa.Integer()),
    )
    selected_team = (
        sa.select(routes.c.unit_id)
        .where(
            routes.c.request_id == requests.c.id,
            routes.c.position == 3,
        )
        .scalar_subquery()
    )
    op.get_bind().execute(
        sa.update(requests)
        .where(selected_team.is_not(None))
        .values(assigned_delivery_team_id=selected_team)
    )


def downgrade() -> None:
    with op.batch_alter_table("service_requests", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_service_requests_assigned_delivery_team_id"))
        batch_op.drop_constraint(
            op.f("fk_service_requests_assigned_delivery_team_id_organisation_units"),
            type_="foreignkey",
        )
        batch_op.drop_column("assigned_delivery_team_id")
