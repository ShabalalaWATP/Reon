"""Typed vocabulary for domain authorisation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PolicyDenial(StrEnum):
    """Internal categories that must never be exposed as object details."""

    ROLE = "ROLE"
    OBJECT_SCOPE = "OBJECT_SCOPE"
    STAGE = "STAGE"
    ASSIGNMENT = "ASSIGNMENT"
    WORK_STATE = "WORK_STATE"
    ACTION = "ACTION"


class RequestOperation(StrEnum):
    CREATE = "CREATE"
    LIST = "LIST"
    VIEW = "VIEW"
    CANCEL = "CANCEL"
    FEEDBACK = "FEEDBACK"
    DOWNLOAD_PRODUCT = "DOWNLOAD_PRODUCT"
    VIEW_UNRELEASED_PRODUCT = "VIEW_UNRELEASED_PRODUCT"
    VIEW_CLARIFICATIONS = "VIEW_CLARIFICATIONS"


class WorkOperation(StrEnum):
    VIEW = "VIEW"
    CLAIM = "CLAIM"
    COMPLETE = "COMPLETE"
    LIST_ELIGIBLE_SPECIALISTS = "LIST_ELIGIBLE_SPECIALISTS"
    VIEW_ROUTING_OPTIONS = "VIEW_ROUTING_OPTIONS"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """A domain decision whose denial detail remains inside the application."""

    denial: PolicyDenial | None = None

    @property
    def allowed(self) -> bool:
        return self.denial is None


ALLOW = PolicyDecision()


def deny(reason: PolicyDenial) -> PolicyDecision:
    return PolicyDecision(reason)
