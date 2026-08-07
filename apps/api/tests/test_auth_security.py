from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from istari_service.auth_service import hash_opaque_token
from istari_service.domain import Actor, SessionRecord
from istari_service.errors import CsrfFailed
from istari_service.models import UserRole
from istari_service.security import require_csrf


def session_record() -> SessionRecord:
    return SessionRecord(
        id=uuid4(),
        actor=Actor(
            id=uuid4(),
            username="requester@example.test",
            display_name="Synthetic Requester",
            role=UserRole.REQUESTER,
            scope="Requesting Area A",
        ),
        csrf_token_hash=hash_opaque_token("csrf-value"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.mark.parametrize(
    "origin",
    ["https://service.example.test", "https://service.example.test/"],
)
def test_require_csrf_accepts_trusted_origin_and_matching_token(origin: str) -> None:
    require_csrf(
        session_record(),
        "csrf-value",
        origin,
        frozenset({"https://service.example.test"}),
    )


@pytest.mark.parametrize(
    "origin",
    [None, "https://untrusted.example.test", "https://service.example.test.evil"],
)
def test_require_csrf_rejects_missing_or_untrusted_origin(origin: str | None) -> None:
    with pytest.raises(CsrfFailed):
        require_csrf(
            session_record(),
            "csrf-value",
            origin,
            frozenset({"https://service.example.test"}),
        )


@pytest.mark.parametrize("token", [None, "", "wrong-value"])
def test_require_csrf_rejects_missing_or_incorrect_token(token: str | None) -> None:
    with pytest.raises(CsrfFailed):
        require_csrf(
            session_record(),
            token,
            "https://service.example.test",
            frozenset({"https://service.example.test"}),
        )
