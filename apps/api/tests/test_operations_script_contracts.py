"""Release and credential-safety contracts for PostgreSQL operations scripts."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from istari_service.maintenance import parser

ROOT = Path(__file__).parents[3]


def _alembic_head() -> str:
    revisions: dict[str, str | None] = {}
    for path in (ROOT / "apps/api/alembic/versions").glob("*.py"):
        tree = ast.parse(path.read_text("utf-8"))
        values: dict[str, str | None] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id in {"revision", "down_revision"}
            ):
                values[node.target.id] = ast.literal_eval(node.value)
        if "revision" in values:
            revisions[str(values["revision"])] = values.get("down_revision")
    parents = {parent for parent in revisions.values() if parent is not None}
    heads = set(revisions) - parents
    assert len(heads) == 1
    return heads.pop()


def test_restore_defaults_track_the_packaged_alembic_head() -> None:
    head = _alembic_head()
    arguments = parser().parse_args(["verify-restore"])
    restore = (ROOT / "scripts/restore-postgres.ps1").read_text("utf-8")
    match = re.search(r"\$ExpectedRevision\s*=\s*'([^']+)'", restore)
    assert match is not None
    assert arguments.expected_revision == match.group(1) == head


def test_postgres_tools_receive_only_a_password_free_service_reference() -> None:
    for name in ("backup-postgres.ps1", "restore-postgres.ps1"):
        script = (ROOT / "scripts" / name).read_text("utf-8")
        assert "--dbname=$env:" not in script
        assert "--dbname=service=istari_maintenance" in script
        assert "New-PostgresServiceFile" in script
        assert "Remove-Item -LiteralPath $serviceFile" in script
    helper = (ROOT / "scripts/lib/PostgresServiceFile.ps1").read_text("utf-8")
    assert "Protect-PostgresServiceFile $path" in helper
    assert "password =" in helper


def test_remote_recovery_requires_authenticated_transport_and_manifests() -> None:
    service_helper = (ROOT / "scripts/lib/PostgresServiceFile.ps1").read_text("utf-8")
    manifest_helper = (ROOT / "scripts/lib/BackupManifest.ps1").read_text("utf-8")
    pester = (ROOT / "scripts/tests/PostgresRecovery.Tests.ps1").read_text("utf-8")
    assert "@('localhost', '127.0.0.1', '[::1]')" in service_helper
    assert "sslmode=verify-full" in service_helper
    assert "ISTARI_POSTGRES_APPROVED_SSL_ROOT_CERT" in service_helper
    assert "HMACSHA256" in manifest_helper
    assert "FixedTimeEquals" in manifest_helper
    assert "coordinated dump and manifest hash change" in pester
