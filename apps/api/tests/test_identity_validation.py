"""Shared email validation and URI-control regressions."""

from __future__ import annotations

import pytest

from mist_service.identity_validation import normalise_email


def test_email_normalisation_preserves_synthetic_and_plus_addresses() -> None:
    assert normalise_email(" CUSTOMER+Tag@EXAMPLE.TEST ") == (
        "customer+tag@example.test"
    )


@pytest.mark.parametrize(
    "value",
    (
        "Display Name <customer@example.test>",
        "customer@@example.test",
        "customer@example.test?bcc=attacker%40example.test",
        "customer@example.test#fragment",
        "customer@example.test&bcc=attacker",
        "customer@example.test%0d%0abcc:attacker@example.test",
        f"{'a' * 244}@example.test",
    ),
)
def test_email_normalisation_rejects_non_address_and_uri_field_syntax(
    value: str,
) -> None:
    with pytest.raises(ValueError, match="valid email address"):
        normalise_email(value)
