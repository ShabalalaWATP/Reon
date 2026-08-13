"""Keyed, privacy-preserving login limiter identifiers."""

from ipaddress import ip_network

import pytest
from fastapi import Request

from istari_service.login_rate_limiter import credential_budget_key, login_source_key

PSEUDONYM_KEY = b"p" * 32


def _request(peer: str | None, *, forwarded: str | None = None) -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    return Request(
        {"type": "http", "headers": headers, "client": (peer, 1) if peer else None}
    )


def test_source_key_ignores_untrusted_forwarding_and_stores_no_address() -> None:
    direct = login_source_key(_request("203.0.113.7"), (), pseudonym_key=PSEUDONYM_KEY)
    forged = login_source_key(
        _request("203.0.113.7", forwarded="198.51.100.9"),
        (),
        pseudonym_key=PSEUDONYM_KEY,
    )
    assert direct == forged
    assert direct == login_source_key(
        _request("::ffff:203.0.113.7"), (), pseudonym_key=PSEUDONYM_KEY
    )
    assert direct.startswith("source:") and len(direct) == 71
    assert "203.0.113.7" not in direct


def test_source_key_accepts_only_one_address_from_an_explicit_proxy() -> None:
    trusted = (ip_network("10.20.0.0/16"),)
    expected = login_source_key(
        _request("198.51.100.9"), (), pseudonym_key=PSEUDONYM_KEY
    )
    assert (
        login_source_key(
            _request("10.20.1.5", forwarded="198.51.100.9"),
            trusted,
            pseudonym_key=PSEUDONYM_KEY,
        )
        == expected
    )
    direct = login_source_key(
        _request("10.20.1.5"), trusted, pseudonym_key=PSEUDONYM_KEY
    )
    for forwarded in ("198.51.100.9, 10.20.1.4", "not-an-address"):
        assert (
            login_source_key(
                _request("10.20.1.5", forwarded=forwarded),
                trusted,
                pseudonym_key=PSEUDONYM_KEY,
            )
            == direct
        )


def test_keys_are_rotatable_domain_separated_and_require_entropy() -> None:
    request = _request("203.0.113.7")
    source = login_source_key(request, (), pseudonym_key=PSEUDONYM_KEY)
    assert source != login_source_key(request, (), pseudonym_key=b"r" * 32)
    credential = credential_budget_key(
        "  Analyst@Example.test ", pseudonym_key=PSEUDONYM_KEY
    )
    assert credential != source and "analyst" not in credential
    assert credential == credential_budget_key(
        "analyst@example.test", pseudonym_key=PSEUDONYM_KEY
    )
    with pytest.raises(ValueError, match="at least 32 bytes"):
        login_source_key(request, (), pseudonym_key=b"short")
