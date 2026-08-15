"""Build the bounded, labelled search projection for a service request."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Protocol

# The validated request contract can contribute fewer than 27,000 characters.
# Keep a defensive ceiling while guaranteeing that every accepted field remains
# represented in the lexical projection.
MAX_SEARCH_TEXT_CHARACTERS = 30_000


class SearchableRequest(Protocol):
    title: str
    description: str
    question_to_answer: str
    desired_outcome: str
    background_context: str
    subject_area_or_location: str
    coverage_start: date
    coverage_end: date
    customer_urgency: Any
    supported_activity_or_decision: str
    required_by: date
    required_by_reason: str
    preferred_deliverable_type: str
    success_criteria: str
    constraints_or_caveats: str
    supporting_information: str
    sensitivity: Any
    handling_instructions: str


@dataclass(frozen=True, slots=True)
class SearchProjectionText:
    title: str
    question: str
    outcome: str
    context: str
    all_fields: str


SEARCH_FIELDS: tuple[tuple[str, str], ...] = (
    ("Title", "title"),
    ("Description", "description"),
    ("Question to answer", "question_to_answer"),
    ("Desired outcome", "desired_outcome"),
    ("Background context", "background_context"),
    ("Subject area or location", "subject_area_or_location"),
    ("Coverage start", "coverage_start"),
    ("Coverage end", "coverage_end"),
    ("Customer urgency", "customer_urgency"),
    ("Supported activity or decision", "supported_activity_or_decision"),
    ("Required by", "required_by"),
    ("Required-by reason", "required_by_reason"),
    ("Preferred deliverable type", "preferred_deliverable_type"),
    ("Success criteria", "success_criteria"),
    ("Constraints or caveats", "constraints_or_caveats"),
    ("Supporting information", "supporting_information"),
    ("Sensitivity", "sensitivity"),
    ("Handling instructions", "handling_instructions"),
)


def normalise_search_value(value: object) -> str:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, date):
        return value.isoformat()
    return " ".join(unicodedata.normalize("NFKC", str(value)).split())


def request_field_values(source: SearchableRequest) -> dict[str, str]:
    return {
        attribute: normalise_search_value(getattr(source, attribute))
        for _, attribute in SEARCH_FIELDS
    }


def build_search_text(source: SearchableRequest) -> SearchProjectionText:
    values = request_field_values(source)
    labelled = [f"{label}: {values[attribute]}" for label, attribute in SEARCH_FIELDS]
    return SearchProjectionText(
        title=values["title"],
        question=values["question_to_answer"],
        outcome=values["desired_outcome"],
        context="\n".join(
            (
                values["background_context"],
                values["subject_area_or_location"],
            )
        ),
        all_fields="\n".join(labelled)[:MAX_SEARCH_TEXT_CHARACTERS],
    )
