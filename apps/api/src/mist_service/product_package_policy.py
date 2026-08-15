"""Immutable compatibility rules pinned when a product package is created."""

from __future__ import annotations

from mist_service.product_errors import ProductConflict, ProductValidationFailed

LEGACY_PACKAGE_POLICY_VERSION = 1
CURRENT_PACKAGE_POLICY_VERSION = 2
SUPPORTED_PACKAGE_POLICY_VERSIONS = frozenset(
    {LEGACY_PACKAGE_POLICY_VERSION, CURRENT_PACKAGE_POLICY_VERSION}
)
IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png"})


def require_supported_policy(policy_version: int) -> None:
    if policy_version not in SUPPORTED_PACKAGE_POLICY_VERSIONS:
        raise ProductConflict("The product package policy version is unsupported.")


def validate_managed_type(policy_version: int, media_type: str) -> None:
    require_supported_policy(policy_version)
    if (
        policy_version == LEGACY_PACKAGE_POLICY_VERSION
        and media_type in IMAGE_MEDIA_TYPES
    ):
        raise ProductValidationFailed(
            "Images are not permitted by this package's pinned policy."
        )


def validate_covering_note(
    policy_version: int, covering_note: str | None
) -> str | None:
    require_supported_policy(policy_version)
    if policy_version == CURRENT_PACKAGE_POLICY_VERSION and covering_note is None:
        raise ProductValidationFailed(
            "A covering note to the Customer is required for this package."
        )
    return covering_note
