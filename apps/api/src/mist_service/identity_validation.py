"""Shared normalisation for managed account email addresses."""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email


def normalise_email(value: str) -> str:
    cleaned = value.strip().lower()
    if len(cleaned) > 254:
        raise ValueError("enter a valid email address")
    try:
        result = validate_email(
            cleaned,
            check_deliverability=False,
            test_environment=True,
        )
    except EmailNotValidError as error:
        raise ValueError("enter a valid email address") from error
    return result.normalized.lower()
