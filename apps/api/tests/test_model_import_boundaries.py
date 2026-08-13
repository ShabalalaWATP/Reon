"""Persistence modules must be safe to import from a clean interpreter."""

from __future__ import annotations

import subprocess
import sys


def test_request_event_model_supports_cold_import() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from istari_service.request_event_models import RequestEvent; "
            "assert RequestEvent.__tablename__ == 'request_events'",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
