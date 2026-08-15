"""Canonical digest for an exact configuration snapshot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from mist_service.configuration_types import ConfigurationDraftSpec


def configuration_digest(specification: ConfigurationDraftSpec) -> str:
    """Return an order-independent SHA-256 digest of routing configuration."""

    template = specification.workflow_template
    payload = {
        "units": sorted(
            (_record(item) for item in specification.units),
            key=lambda item: (item["unit_id"], item["effective_from"]),
        ),
        "edges": sorted(
            (_record(item) for item in specification.edges),
            key=lambda item: (item["child_unit_id"], item["effective_from"]),
        ),
        "candidate_groups": sorted(
            (_record(item) for item in specification.candidate_groups),
            key=lambda item: (item["unit_id"], item["purpose"]),
        ),
        "workflow_template": _record(template),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _record(value: object) -> dict[str, Any]:
    fields = getattr(value, "__dataclass_fields__", None)
    if fields is None:
        raise TypeError("configuration digest records must be dataclasses")
    return {name: _normalise(getattr(value, name)) for name in fields}


def _normalise(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, (UUID, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value
