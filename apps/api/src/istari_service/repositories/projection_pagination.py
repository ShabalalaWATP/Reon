"""Opaque keyset cursors shared by personal projections."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from istari_service.errors import ServiceError


class InvalidProjectionQuery(ServiceError):
    status_code = 422
    code = "INVALID_PROJECTION_QUERY"
    public_message = "The projection filters are invalid."


def encode_cursor(changed_at: datetime, item_id: UUID) -> str:
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=UTC)
    payload = json.dumps([changed_at.isoformat(), str(item_id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str, *, message: str) -> tuple[datetime, UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        changed_at_raw, item_id_raw = json.loads(
            base64.urlsafe_b64decode(padded).decode()
        )
        changed_at = datetime.fromisoformat(changed_at_raw)
        if changed_at.tzinfo is None:
            raise ValueError
        return changed_at, UUID(item_id_raw)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise InvalidProjectionQuery(message) from error
