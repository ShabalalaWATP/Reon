"""Compatibility and OpenAPI contracts for split policy and schema families."""

from __future__ import annotations

import istari_service.policies as policies
import istari_service.request_access_policy as request_policy
import istari_service.schemas.configuration as configuration
import istari_service.schemas.configuration_inputs as configuration_inputs
import istari_service.schemas.configuration_results as configuration_results
import istari_service.work_access_policy as work_policy
from istari_service.config import Environment, Settings
from istari_service.main import create_app


def test_policy_facade_preserves_public_callable_identities() -> None:
    assert policies.decide_request_access is request_policy.decide_request_access
    assert (
        policies.has_self_request_conflict is request_policy.has_self_request_conflict
    )
    assert policies.ROLE_BY_STAGE is request_policy.ROLE_BY_STAGE
    assert policies.decide_work_access is work_policy.decide_work_access
    assert policies.decide_work_completion is work_policy.decide_work_completion
    assert policies.ACTIONS_BY_STAGE is work_policy.ACTIONS_BY_STAGE


def test_configuration_facade_preserves_public_schema_identities() -> None:
    assert (
        configuration.ConfigurationDraftCreate
        is configuration_inputs.ConfigurationDraftCreate
    )
    assert (
        configuration.ConfigurationReasonCommand
        is configuration_inputs.ConfigurationReasonCommand
    )
    assert (
        configuration.ConfigurationVersionDetail
        is configuration_results.ConfigurationVersionDetail
    )
    assert (
        configuration.RequestConfigurationPinView
        is configuration_results.RequestConfigurationPinView
    )


def test_configuration_openapi_keeps_stable_schema_names_and_aliases() -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
        allow_demo_users=False,
        configuration_admin_enabled=True,
    )
    document = create_app(settings=settings).openapi()
    schemas = document["components"]["schemas"]

    assert {
        "ConfigurationDraftCreate",
        "ConfigurationReasonCommand",
        "ConfigurationVersionDetail",
    } <= schemas.keys()
    assert "effectiveFrom" in schemas["ConfigurationDraftCreate"]["properties"]
    assert "basedOnVersionId" in schemas["ConfigurationVersionDetail"]["properties"]
    assert "/api/v1/admin/configuration/versions" in document["paths"]
