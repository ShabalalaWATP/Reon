"""Enforce immutable and attributable legal-hold evidence."""

from alembic import op

revision: str = "0041_legal_hold_immutability"
down_revision: str | None = "0040_request_event_staff_default"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE legal_holds
        ADD CONSTRAINT legal_holds_release_attribution
        CHECK ((released_at IS NULL) = (released_by IS NULL))
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_legal_hold_evidence() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'legal-hold evidence is append-only';
            END IF;
            IF NEW.target_type IS DISTINCT FROM OLD.target_type
               OR NEW.target_id IS DISTINCT FROM OLD.target_id
               OR NEW.reason_code IS DISTINCT FROM OLD.reason_code
               OR NEW.authorised_by IS DISTINCT FROM OLD.authorised_by
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'legal-hold application evidence is immutable';
            END IF;
            IF OLD.released_at IS NOT NULL AND ROW(
                NEW.released_at, NEW.released_by
            ) IS DISTINCT FROM ROW(OLD.released_at, OLD.released_by) THEN
                RAISE EXCEPTION 'legal-hold release evidence is immutable';
            END IF;
            IF (NEW.released_at IS NULL) <> (NEW.released_by IS NULL) THEN
                RAISE EXCEPTION 'legal-hold release evidence must be attributable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_protect_legal_hold_evidence
        BEFORE UPDATE OR DELETE ON legal_holds
        FOR EACH ROW EXECUTE FUNCTION protect_legal_hold_evidence()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_protect_legal_hold_evidence ON legal_holds")
    op.execute("DROP FUNCTION IF EXISTS protect_legal_hold_evidence()")
    op.execute(
        "ALTER TABLE legal_holds DROP CONSTRAINT legal_holds_release_attribution"
    )
