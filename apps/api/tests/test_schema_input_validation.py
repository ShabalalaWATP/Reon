"""Boundary validation for user-controlled request and workflow inputs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from istari_service.schemas.requests import RequestCreate, Sensitivity
from istari_service.schemas.work import (
    AllocateRequest,
    CloseRequest,
    ReleaseDeliverable,
    SubmitDeliverable,
)


def _request_create(**overrides: object) -> RequestCreate:
    values: dict[str, object] = {
        "title": "Synthetic request",
        "service_category": "Research",
        "description": "A synthetic description long enough for validation.",
        "desired_outcome": "A synthetic outcome for validation.",
        "background_context": "Synthetic context",
        "required_by": datetime.now(UTC).date() + timedelta(days=7),
        "required_by_reason": "Synthetic deadline",
        "preferred_deliverable_type": "Brief",
        "success_criteria": "Synthetic success criteria",
        "requesting_business_area": "Synthetic area",
        "intended_recipients": ["Synthetic recipient"],
        "sensitivity": Sensitivity.STANDARD,
        "handling_instructions": "Synthetic handling",
    }
    values.update(overrides)
    return RequestCreate.model_validate(values)


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: _request_create(title="   "), "title"),
        (lambda: CloseRequest(action="close", reason="   "), "reason"),
        (
            lambda: SubmitDeliverable(
                action="submit",
                deliverable_title="Synthetic deliverable",
                deliverable_text="   ",
            ),
            "deliverable_text",
        ),
    ],
)
def test_whitespace_only_required_text_is_rejected(
    factory: Callable[[], object],
    field: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        factory()

    assert field in str(error.value)


def test_request_recipient_uniqueness_is_checked_after_trimming() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        _request_create(
            intended_recipients=["Synthetic recipient", " Synthetic recipient "],
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda values: AllocateRequest(
            action="allocate",
            destination_unit_id=uuid4(),
            required_capabilities=values,
        ),
        lambda values: ReleaseDeliverable(action="release", recipients=values),
    ],
)
def test_workflow_string_lists_are_trimmed(
    factory: Callable[[list[str]], AllocateRequest | ReleaseDeliverable],
) -> None:
    payload = factory(["  Synthetic value  "])

    value = (
        payload.required_capabilities
        if isinstance(payload, AllocateRequest)
        else payload.recipients
    )
    assert value == ["Synthetic value"]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (["   "], "1 to 120"),
        (["x" * 121], "1 to 120"),
        (["Synthetic", " Synthetic "], "must be unique"),
    ],
)
@pytest.mark.parametrize(
    "factory",
    [
        lambda values: AllocateRequest(
            action="allocate",
            destination_unit_id=uuid4(),
            required_capabilities=values,
        ),
        lambda values: ReleaseDeliverable(action="release", recipients=values),
    ],
)
def test_workflow_string_lists_reject_unsafe_values(
    factory: Callable[[list[str]], AllocateRequest | ReleaseDeliverable],
    values: list[str],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        factory(values)
