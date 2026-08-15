"""Pytest entry point for the executable PostgreSQL migration assurance."""

from __future__ import annotations

import os

import pytest

from postgres_migration_roundtrip import run_postgres_migration_roundtrip


def test_postgres_revisions_0043_to_0047_round_trip() -> None:
    database_url = os.getenv("MIST_POSTGRES_TEST_URL")
    required = os.getenv("MIST_REQUIRE_POSTGRES_TESTS") == "true"
    if not required:
        pytest.skip("migration assurance runs in the explicit PostgreSQL CI lane")
    if not database_url:
        pytest.fail("mandatory PostgreSQL migration URL is not configured")
    run_postgres_migration_roundtrip(database_url)
