"""Add bounded self-declared operational skills to user profiles.

Revision ID: 0030_team_operational_skills
Revises: 0029_related_request_search
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_team_operational_skills"
down_revision: str | None = "0029_related_request_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("skills", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "skills")
