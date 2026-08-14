"""External product-link validation without DNS resolution or network access."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from istari_service.product_errors import ProductValidationFailed


class AllowedHttpsLinkPolicy:
    """Validate exact allow-listed domains without resolving or fetching URLs."""

    def __init__(self, allowed_domains: frozenset[str]) -> None:
        self._allowed = frozenset(self._domain(item) for item in allowed_domains)

    def normalise(self, destination: str) -> tuple[str, str]:
        if (
            not destination
            or any(ord(char) < 32 for char in destination)
            or "\\" in destination
        ):
            raise ProductValidationFailed("The external product link is invalid.")
        parsed = urlsplit(destination)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            ) from exc
        if port not in {None, 443}:
            raise ProductValidationFailed(
                "An approved absolute HTTPS link is required."
            )
        domain = self._domain(parsed.hostname)
        try:
            address = ipaddress.ip_address(domain)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ProductValidationFailed(
                "Private-network product links are forbidden."
            )
        if domain not in self._allowed:
            raise ProductValidationFailed(
                "The external product domain is not approved."
            )
        path = parsed.path or "/"
        return urlunsplit(("https", domain, path, parsed.query, "")), domain

    @staticmethod
    def _domain(value: str) -> str:
        try:
            return value.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ProductValidationFailed(
                "The external product domain is invalid."
            ) from exc
