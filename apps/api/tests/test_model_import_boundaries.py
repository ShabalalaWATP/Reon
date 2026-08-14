"""Persistence modules must be safe to import from a clean interpreter."""

from __future__ import annotations

import subprocess
import sys


def _run_cold_import(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - interpreter and source are test-owned
        [sys.executable, "-c", source],
        capture_output=True,
        check=False,
        text=True,
    )


def test_request_event_model_supports_cold_import() -> None:
    completed = _run_cold_import(
        "from istari_service.request_event_models import RequestEvent; "
        "assert RequestEvent.__tablename__ == 'request_events'"
    )
    assert completed.returncode == 0, completed.stderr


def test_leaf_models_do_not_load_core_models_or_registry() -> None:
    completed = _run_cold_import(
        "import sys; "
        "from istari_service.deliverable_model import Deliverable; "
        "from istari_service.feedback_model import Feedback; "
        "from istari_service.outbox_model import WorkflowOutbox; "
        "assert Deliverable.__tablename__ == 'deliverables'; "
        "assert Feedback.__tablename__ == 'feedback'; "
        "assert WorkflowOutbox.__tablename__ == 'workflow_outbox'; "
        "assert 'istari_service.models' not in sys.modules; "
        "assert 'istari_service.model_registry' not in sys.modules"
    )
    assert completed.returncode == 0, completed.stderr


def test_core_compatibility_exports_do_not_load_registry() -> None:
    completed = _run_cold_import(
        "import sys; "
        "from istari_service.models import Deliverable, Feedback, WorkflowOutbox; "
        "assert Deliverable.__tablename__ == 'deliverables'; "
        "assert Feedback.__tablename__ == 'feedback'; "
        "assert WorkflowOutbox.__tablename__ == 'workflow_outbox'; "
        "assert 'istari_service.model_registry' not in sys.modules"
    )
    assert completed.returncode == 0, completed.stderr


def test_registry_registers_complete_metadata_from_a_cold_import() -> None:
    completed = _run_cold_import(
        "from istari_service.model_registry import Base; "
        "assert len(Base.metadata.tables) == 91; "
        "assert {'users', 'service_requests', 'deliverables', 'feedback', "
        "'product_packages', 'workflow_outbox'} <= set(Base.metadata.tables)"
    )
    assert completed.returncode == 0, completed.stderr
