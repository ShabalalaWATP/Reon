"""Seal reviewed configuration snapshots and bind approval digests.

Revision ID: 0018_configuration_sealing
Revises: 0017_legacy_workflow_identity
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0018_configuration_sealing"
down_revision: str | None = "0017_legacy_workflow_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY_DIGEST = "0" * 64
_CREATE_COMPONENT_GUARDS = (
    """CREATE TRIGGER guard_configuration_unit_revisions
    BEFORE INSERT OR UPDATE OR DELETE ON public.configuration_unit_revisions
    FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_component()""",
    """CREATE TRIGGER guard_configuration_hierarchy_edges
    BEFORE INSERT OR UPDATE OR DELETE ON public.configuration_hierarchy_edges
    FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_component()""",
    """CREATE TRIGGER guard_configuration_candidate_groups
    BEFORE INSERT OR UPDATE OR DELETE ON public.configuration_candidate_groups
    FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_component()""",
    """CREATE TRIGGER guard_configuration_workflow_templates
    BEFORE INSERT OR UPDATE OR DELETE ON public.configuration_workflow_templates
    FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_component()""",
)
_DROP_COMPONENT_GUARDS = (
    "DROP TRIGGER IF EXISTS guard_configuration_workflow_templates "
    "ON public.configuration_workflow_templates",
    "DROP TRIGGER IF EXISTS guard_configuration_candidate_groups "
    "ON public.configuration_candidate_groups",
    "DROP TRIGGER IF EXISTS guard_configuration_hierarchy_edges "
    "ON public.configuration_hierarchy_edges",
    "DROP TRIGGER IF EXISTS guard_configuration_unit_revisions "
    "ON public.configuration_unit_revisions",
)
_UUID_COLUMNS = {
    "unit_id",
    "parent_unit_id",
    "child_unit_id",
    "organisation_root_id",
    "workflow_definition_id",
}
_JSON_COLUMNS = {
    "allowed_outcomes",
    "approved_link_domains",
    "artefact_types",
    "core_fields",
    "product_types",
    "reminder_days",
    "service_categories",
    "task_labels",
}


def upgrade() -> None:
    with op.batch_alter_table("configuration_approvals") as batch_op:
        batch_op.add_column(
            sa.Column(
                "snapshot_digest",
                sa.String(length=64),
                nullable=False,
                server_default=_EMPTY_DIGEST,
            )
        )
    with op.batch_alter_table("configuration_activations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "snapshot_digest",
                sa.String(length=64),
                nullable=False,
                server_default=_EMPTY_DIGEST,
            )
        )
    _backfill_snapshot_digests()
    with op.batch_alter_table("configuration_approvals") as batch_op:
        batch_op.alter_column("snapshot_digest", server_default=None)
    with op.batch_alter_table("configuration_activations") as batch_op:
        batch_op.alter_column("snapshot_digest", server_default=None)
    if op.get_bind().dialect.name == "postgresql":
        _create_postgres_guards()


def _backfill_snapshot_digests() -> None:
    connection = op.get_bind()
    version_ids = connection.execute(
        sa.text(
            "SELECT configuration_version_id FROM configuration_approvals "
            "UNION SELECT configuration_version_id FROM configuration_activations"
        )
    ).scalars()
    for version_id in version_ids:
        digest = _stored_snapshot_digest(connection, version_id)
        parameters = {"digest": digest, "version_id": version_id}
        connection.execute(
            sa.text(
                "UPDATE configuration_approvals SET snapshot_digest = :digest "
                "WHERE configuration_version_id = :version_id"
            ),
            parameters,
        )
        connection.execute(
            sa.text(
                "UPDATE configuration_activations SET snapshot_digest = :digest "
                "WHERE configuration_version_id = :version_id"
            ),
            parameters,
        )


def _stored_snapshot_digest(connection: sa.Connection, version_id: object) -> str:
    units = _records(
        connection,
        "configuration_unit_revisions",
        version_id,
        (
            "unit_id",
            "code",
            "name",
            "kind",
            "effective_from",
            "effective_until",
            "routing_enabled",
            "minimum_managers",
            "minimum_analysts",
        ),
    )
    edges = _records(
        connection,
        "configuration_hierarchy_edges",
        version_id,
        (
            "parent_unit_id",
            "child_unit_id",
            "effective_from",
            "effective_until",
        ),
    )
    groups = _records(
        connection,
        "configuration_candidate_groups",
        version_id,
        ("unit_id", "purpose", "candidate_group"),
    )
    templates = _records(
        connection,
        "configuration_workflow_templates",
        version_id,
        (
            "schema_id",
            "form_version",
            "notification_policy_version",
            "organisation_root_id",
            "route_depth",
            "core_fields",
            "service_categories",
            "product_types",
            "task_labels",
            "allowed_outcomes",
            "reminder_days",
            "artefact_types",
            "approved_link_domains",
            "workflow_definition_id",
        ),
    )
    if len(templates) != 1:
        raise RuntimeError(
            "configuration digest backfill requires one workflow template"
        )
    for field_name in (
        "core_fields",
        "service_categories",
        "product_types",
        "reminder_days",
        "artefact_types",
        "approved_link_domains",
    ):
        templates[0][field_name] = sorted(templates[0][field_name])
    templates[0]["allowed_outcomes"] = {
        key: sorted(values) for key, values in templates[0]["allowed_outcomes"].items()
    }
    payload = {
        "units": sorted(
            units, key=lambda item: (item["unit_id"], item["effective_from"])
        ),
        "edges": sorted(
            edges,
            key=lambda item: (item["child_unit_id"], item["effective_from"]),
        ),
        "candidate_groups": sorted(
            groups, key=lambda item: (item["unit_id"], item["purpose"])
        ),
        "workflow_template": templates[0],
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _records(
    connection: sa.Connection,
    table: str,
    version_id: object,
    columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    source = sa.table(
        table,
        sa.column("configuration_version_id"),
        *(sa.column(column) for column in columns),
    )
    rows = connection.execute(
        sa.select(*(source.c[column] for column in columns)).where(
            source.c.configuration_version_id == version_id
        )
    ).mappings()
    return [
        {column: _normalise_field(column, row[column]) for column in columns}
        for row in rows
    ]


def _normalise_field(column: str, value: Any) -> Any:
    if column in _UUID_COLUMNS and value is not None:
        return str(UUID(str(value)))
    if column in {"effective_from", "effective_until"} and value is not None:
        parsed = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
        aware = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
        return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if column == "routing_enabled":
        return bool(value)
    if column in _JSON_COLUMNS and isinstance(value, str):
        try:
            return _normalise(json.loads(value))
        except json.JSONDecodeError:
            return value
    return _normalise(value)


def _normalise(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, (UUID, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def _create_postgres_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION public.guard_configuration_approval_insert() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        DECLARE
            candidate public.configuration_versions%ROWTYPE;
            reviewer public.users%ROWTYPE;
        BEGIN
            SELECT * INTO candidate FROM public.configuration_versions
             WHERE id = NEW.configuration_version_id FOR SHARE;
            SELECT * INTO reviewer FROM public.users
             WHERE id = NEW.actor_user_id FOR SHARE;
            IF candidate.id IS NULL OR candidate.status <> 'AWAITING_APPROVAL' OR
               NEW.reviewed_version <> candidate.version OR
               NEW.actor_user_id = candidate.created_by_user_id OR
               reviewer.id IS NULL OR reviewer.role <> 'PLATFORM_ADMIN' OR
               reviewer.is_active IS NOT TRUE OR
               NEW.snapshot_digest !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'invalid configuration approval evidence'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER guard_configuration_approval_inserts
        BEFORE INSERT ON public.configuration_approvals
        FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_approval_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.guard_configuration_activation_insert() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        DECLARE
            candidate public.configuration_versions%ROWTYPE;
            evidence public.configuration_approvals%ROWTYPE;
            activator public.users%ROWTYPE;
        BEGIN
            SELECT * INTO candidate FROM public.configuration_versions
             WHERE id = NEW.configuration_version_id FOR SHARE;
            SELECT * INTO evidence FROM public.configuration_approvals
             WHERE id = NEW.approval_id FOR SHARE;
            SELECT * INTO activator FROM public.users
             WHERE id = NEW.activated_by_user_id FOR SHARE;
            IF candidate.id IS NULL OR candidate.status <> 'ACTIVE' OR
               evidence.id IS NULL OR evidence.decision <> 'APPROVED' OR
               evidence.configuration_version_id <> candidate.id OR
               evidence.snapshot_digest <> NEW.snapshot_digest OR
               candidate.version <> evidence.reviewed_version + 2 OR
               NEW.superseded_version_id IS DISTINCT FROM candidate.based_on_version_id OR
               NEW.activated_at < evidence.created_at OR
               NEW.activated_by_user_id = candidate.created_by_user_id OR
               activator.id IS NULL OR activator.role <> 'PLATFORM_ADMIN' OR
               activator.is_active IS NOT TRUE THEN
                RAISE EXCEPTION 'invalid configuration activation evidence'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER guard_configuration_activation_inserts
        BEFORE INSERT ON public.configuration_activations
        FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_activation_insert()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.guard_configuration_component() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        DECLARE
            target_version uuid;
            target_status text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_version := OLD.configuration_version_id;
            ELSE
                IF TG_OP = 'UPDATE' AND
                   OLD.configuration_version_id IS DISTINCT FROM NEW.configuration_version_id THEN
                    RAISE EXCEPTION 'configuration component ownership is immutable'
                        USING ERRCODE = '42501';
                END IF;
                target_version := NEW.configuration_version_id;
            END IF;
            SELECT status INTO target_status
              FROM public.configuration_versions
             WHERE id = target_version FOR SHARE;
            IF target_status IS DISTINCT FROM 'DRAFT' THEN
                RAISE EXCEPTION 'configuration snapshot is sealed'
                    USING ERRCODE = '42501';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    for statement in _CREATE_COMPONENT_GUARDS:
        op.execute(statement)
    op.execute(
        """
        CREATE FUNCTION public.guard_configuration_version() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        BEGIN
            IF OLD.status <> 'DRAFT' AND (
                NEW.label IS DISTINCT FROM OLD.label OR
                NEW.effective_from IS DISTINCT FROM OLD.effective_from OR
                NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
                NEW.based_on_version_id IS DISTINCT FROM OLD.based_on_version_id
            ) THEN
                RAISE EXCEPTION 'configuration identity is sealed'
                    USING ERRCODE = '42501';
            END IF;
            IF NOT (
                (OLD.status = 'DRAFT' AND NEW.status IN ('DRAFT', 'VALIDATED')) OR
                (OLD.status = 'VALIDATED' AND NEW.status IN ('DRAFT', 'VALIDATED', 'AWAITING_APPROVAL')) OR
                (OLD.status = 'AWAITING_APPROVAL' AND NEW.status IN ('AWAITING_APPROVAL', 'REJECTED', 'ACTIVE')) OR
                (OLD.status = 'ACTIVE' AND NEW.status IN ('ACTIVE', 'SUPERSEDED')) OR
                (OLD.status = 'REJECTED' AND NEW.status = 'REJECTED') OR
                (OLD.status = 'SUPERSEDED' AND NEW.status = 'SUPERSEDED')
            ) THEN
                RAISE EXCEPTION 'invalid configuration lifecycle transition'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.status NOT IN ('DRAFT', 'VALIDATED') AND
               NEW.reason IS DISTINCT FROM OLD.reason THEN
                RAISE EXCEPTION 'configuration reason is sealed'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.status = 'AWAITING_APPROVAL' AND NEW.status = 'ACTIVE' AND
               NOT EXISTS (
                   SELECT 1 FROM public.configuration_approvals
                    WHERE configuration_version_id = OLD.id
                      AND decision = 'APPROVED'
               ) THEN
                RAISE EXCEPTION 'approved configuration evidence is required'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.guard_workflow_definition() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR
               NEW.process_id IS DISTINCT FROM OLD.process_id OR
               NEW.process_version IS DISTINCT FROM OLD.process_version OR
               NEW.compatibility_key IS DISTINCT FROM OLD.compatibility_key OR
               NEW.checksum IS DISTINCT FROM OLD.checksum OR
               NEW.approved_by_user_id IS DISTINCT FROM OLD.approved_by_user_id OR
               NEW.approved_at IS DISTINCT FROM OLD.approved_at THEN
                RAISE EXCEPTION 'approved workflow identity is sealed'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER guard_approved_workflow_definitions
        BEFORE UPDATE OR DELETE ON public.approved_workflow_definitions
        FOR EACH ROW EXECUTE FUNCTION public.guard_workflow_definition()
        """
    )
    op.execute(
        """
        CREATE TRIGGER guard_configuration_versions
        BEFORE UPDATE ON public.configuration_versions
        FOR EACH ROW EXECUTE FUNCTION public.guard_configuration_version()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS guard_configuration_activation_inserts "
            "ON public.configuration_activations"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS public.guard_configuration_activation_insert()"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS guard_configuration_approval_inserts "
            "ON public.configuration_approvals"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS public.guard_configuration_approval_insert()"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS guard_approved_workflow_definitions "
            "ON public.approved_workflow_definitions"
        )
        op.execute("DROP FUNCTION IF EXISTS public.guard_workflow_definition()")
        op.execute(
            "DROP TRIGGER IF EXISTS guard_configuration_versions ON public.configuration_versions"
        )
        op.execute("DROP FUNCTION IF EXISTS public.guard_configuration_version()")
        for statement in _DROP_COMPONENT_GUARDS:
            op.execute(statement)
        op.execute("DROP FUNCTION IF EXISTS public.guard_configuration_component()")
    with op.batch_alter_table("configuration_activations") as batch_op:
        batch_op.drop_column("snapshot_digest")
    with op.batch_alter_table("configuration_approvals") as batch_op:
        batch_op.drop_column("snapshot_digest")
