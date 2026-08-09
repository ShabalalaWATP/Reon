"""ClamAV signature provenance and network-boundary contracts."""

from __future__ import annotations

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_scanner_daemon_and_signature_updater_are_isolated() -> None:
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    daemon = services["clamav"]
    updater = services["clamav-updater"]

    assert daemon["networks"] == ["scanner"]
    assert updater["networks"] == ["signature-updates"]
    assert compose["networks"]["scanner"]["internal"] is True
    assert not (compose["networks"]["signature-updates"] or {}).get("internal", False)
    assert daemon["depends_on"] == {"clamav-updater": {"condition": "service_healthy"}}
    assert daemon["environment"]["CLAMAV_NO_FRESHCLAMD"] == "true"
    assert updater["environment"]["CLAMAV_NO_CLAMD"] == "true"
    assert updater["environment"]["CLAMAV_HEALTH_CHECK_DAEMON"] == "false"


def test_both_clamav_processes_run_with_minimum_container_privilege() -> None:
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    daemon = compose["services"]["clamav"]
    updater = compose["services"]["clamav-updater"]

    for service in (daemon, updater):
        assert service["user"] == "100:101"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service.get("ports", []) == []
    assert daemon["volumes"] == ["clamav-data:/var/lib/clamav:ro"]
    assert updater["volumes"] == ["clamav-data:/var/lib/clamav"]


def test_healthcheck_uses_signed_build_metadata_not_file_mtime() -> None:
    healthcheck = (REPOSITORY_ROOT / "infra" / "clamav" / "healthcheck.sh").read_text(
        encoding="utf-8"
    )
    dockerfile = (REPOSITORY_ROOT / "infra" / "clamav" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert '$1 == "Build time"' in healthcheck
    assert "stat -c" not in healthcheck
    assert "USER 100:101" in dockerfile
    assert 'ENTRYPOINT ["/init-unprivileged"]' in dockerfile
