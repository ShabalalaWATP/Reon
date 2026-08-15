"""Keep the approved workflow seed bound to the bundled BPMN bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from mist_service.configuration_seed import BUNDLED_BPMN_CHECKSUM


def test_bundled_workflow_checksum_matches_approved_seed() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    bpmn = repository_root / "workflow" / "service-request.bpmn"

    assert hashlib.sha256(bpmn.read_bytes()).hexdigest() == BUNDLED_BPMN_CHECKSUM
