"""Camunda SDK configuration shared by API and worker processes."""

from __future__ import annotations

from mist_service.config import Settings


def camunda_client_configuration(settings: Settings) -> dict[str, str]:
    address = settings.camunda_base_url
    if not address.endswith("/v2"):
        address = f"{address}/v2"
    auth_strategy = settings.camunda_auth_mode.upper()
    if auth_strategy not in {"NONE", "BASIC"}:
        raise ValueError("only NONE or BASIC Camunda authentication is configured")
    configuration = {
        "CAMUNDA_REST_ADDRESS": address,
        "CAMUNDA_AUTH_STRATEGY": auth_strategy,
        "CAMUNDA_SDK_LOG_LEVEL": "warn",
    }
    if auth_strategy == "BASIC":
        configuration["CAMUNDA_BASIC_AUTH_USERNAME"] = settings.camunda_username or ""
        configuration["CAMUNDA_BASIC_AUTH_PASSWORD"] = (
            settings.camunda_password.get_secret_value()
            if settings.camunda_password
            else ""
        )
    return configuration
