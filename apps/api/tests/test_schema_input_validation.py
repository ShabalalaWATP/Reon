"""Boundary validation for user-controlled request and workflow inputs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mist_service.schemas.requests import RequestCreate, Sensitivity
from mist_service.schemas.work import (
    AllocateRequest,
    CloseRequest,
    ReleaseDeliverable,
    SubmitDeliverable,
)


def _request_create(**overrides: object) -> RequestCreate:
    values: dict[str, object] = {
        "title": "Synthetic request",
        "description": "A synthetic description long enough for validation.",
        "question_to_answer": "What does the synthetic evidence show?",
        "desired_outcome": "A synthetic outcome for validation.",
        "background_context": "Synthetic context",
        "subject_area_or_location": "Synthetic subject area",
        "coverage_start": datetime.now(UTC).date(),
        "coverage_end": datetime.now(UTC).date() + timedelta(days=1),
        "customer_urgency": "ROUTINE",
        "supported_activity_or_decision": "A fictional planning decision.",
        "required_by": datetime.now(UTC).date() + timedelta(days=7),
        "required_by_reason": "Synthetic deadline",
        "preferred_deliverable_type": "Brief",
        "success_criteria": "Synthetic success criteria",
        "constraints_or_caveats": "No known constraints.",
        "supporting_information": "No supporting material is available.",
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


def test_request_coverage_period_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="must not be before"):
        _request_create(
            coverage_start=datetime.now(UTC).date() + timedelta(days=2),
            coverage_end=datetime.now(UTC).date(),
        )


def test_request_required_date_cannot_be_in_the_past() -> None:
    with pytest.raises(ValidationError, match="must not be in the past"):
        _request_create(required_by=datetime.now(UTC).date() - timedelta(days=1))


def test_customer_cannot_classify_the_internal_service_category() -> None:
    with pytest.raises(ValidationError, match="service_category"):
        _request_create(service_category="Customer-selected category")


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
