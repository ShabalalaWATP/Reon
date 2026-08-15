"""Managed-product command validation coverage."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from mist_service.schemas.products import SubmitPackageCommand


def test_covering_note_is_trimmed_and_cannot_be_only_whitespace() -> None:
    values = {"expected_version": 1, "idempotency_key": uuid4()}
    command = SubmitPackageCommand(**values, covering_note="  Customer note.  ")
    assert command.covering_note == "Customer note."
    with pytest.raises(ValidationError):
        SubmitPackageCommand(**values, covering_note="   ")
