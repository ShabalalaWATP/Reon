"""Replace deprecated coordination presentation values."""

from alembic import op

revision: str = "0032_coordination_language"
down_revision: str | None = "0031_role_aware_action_links"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET scope = 'Shared request coordination' "
        "WHERE scope = 'Shared command routing'"
    )
    op.execute(
        "UPDATE service_requests SET current_owner = 'Request Coordination' "
        "WHERE current_owner = 'Command Routing'"
    )
    op.execute(
        "UPDATE action_projections SET current_owner = 'Request Coordination' "
        "WHERE current_owner = 'Command Routing'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE action_projections SET current_owner = 'Command Routing' "
        "WHERE current_owner = 'Request Coordination'"
    )
    op.execute(
        "UPDATE service_requests SET current_owner = 'Command Routing' "
        "WHERE current_owner = 'Request Coordination'"
    )
    op.execute(
        "UPDATE users SET scope = 'Shared command routing' "
        "WHERE scope = 'Shared request coordination'"
    )
