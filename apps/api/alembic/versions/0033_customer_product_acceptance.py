"""Record explicit Customer acceptance of a dissemination."""

import sqlalchemy as sa
from alembic import op

revision: str = "0033_customer_product_acceptance"
down_revision: str | None = "0032_coordination_language"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "product_disseminations",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "product_disseminations",
        sa.Column("acceptance_key", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_product_disseminations_acceptance_key",
        "product_disseminations",
        ["acceptance_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_product_disseminations_acceptance_key",
        "product_disseminations",
        type_="unique",
    )
    op.drop_column("product_disseminations", "acceptance_key")
    op.drop_column("product_disseminations", "accepted_at")
