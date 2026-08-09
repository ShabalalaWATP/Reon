"""Unicode normalisation for security-sensitive display text."""

import unicodedata


def normalise_display_name(value: str) -> str:
    """Return a canonical display name without invisible control characters."""
    normalised = unicodedata.normalize("NFKC", value).strip()
    if not 2 <= len(normalised) <= 120:
        raise ValueError("name must contain 2 to 120 visible characters")
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in normalised):
        raise ValueError("name cannot contain control or bidirectional characters")
    return normalised
