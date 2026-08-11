"""Shared normalisation for managed account email addresses."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def normalise_email(value: str) -> str:
    cleaned = value.strip().lower()
    if len(cleaned) > 254 or EMAIL_PATTERN.fullmatch(cleaned) is None:
        raise ValueError("enter a valid email address")
    return cleaned
