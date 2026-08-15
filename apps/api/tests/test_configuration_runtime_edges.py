"""Fail-closed branches for immutable request policy and runtime readiness."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mist_service.configuration_readiness import configuration_runtime_is_ready
from mist_service.configuration_request_policy import (
    canonical_link_domains,
    parse_request_configuration_policy,
)
from mist_service.configuration_types import ConfigurationStatus
from mist_service.errors import InvalidAction
from mist_service.organisation_models import OrganisationKind
from mist_service.workflow_start_identity import (
    pinned_start_identity_matches,
    pinned_workflow_identity,
)


def _snapshot() -> dict[str, object]:
    root_id, team_id = uuid4(), uuid4()
    domains, digest = canonical_link_domains(["products.example.test"])
    return {
        "requestPolicySchema": "istari.request-policy/v1",
        "configurationSequence": 2,
        "organisation": {
            "rootUnitId": str(root_id),
            "units": [
                {
                    "unitId": str(root_id),
                    "code": "CRIOC",
                    "name": "CRIOC",
                    "kind": "ROOT",
                    "routingEnabled": True,
                    "staffingStatus": "ROUTING_POOL",
                    "sortOrder": 0,
                },
                {
                    "unitId": str(team_id),
                    "code": "SYNTHETIC_TEAM",
                    "name": "Synthetic Team",
                    "kind": "TEAM",
                    "routingEnabled": True,
                    "staffingStatus": "STAFFED",
                    "sortOrder": 1,
                },
            ],
            "edges": [{"parentUnitId": str(root_id), "childUnitId": str(team_id)}],
            "candidateGroups": [
                {
                    "unitId": str(team_id),
                    "purpose": "MANAGER",
                    "candidateGroup": "synthetic-managers",
                },
                {
                    "unitId": str(team_id),
                    "purpose": "ANALYST",
                    "candidateGroup": "synthetic-analysts",
                },
            ],
        },
        "catalogue": {
            "serviceCategories": ["Research"],
            "productTypes": ["Written summary"],
            "artefactTypes": ["PDF"],
        },
        "approvedLinkDomains": list(domains),
        "approvedLinkDomainsDigest": digest,
    }


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("requestPolicySchema",), "unsupported"),
        (("organisation",), []),
        (("organisation", "units"), {}),
        (("organisation", "units", 0, "routingEnabled"), "yes"),
        (("organisation", "units", 0, "code"), ""),
        (("organisation", "units", 0, "sortOrder"), -1),
        (("configurationSequence",), 0),
        (("approvedLinkDomainsDigest",), "0" * 64),
    ],
)
def test_malformed_pinned_policy_fails_closed(
    path: tuple[str | int, ...], value: object
) -> None:
    snapshot = deepcopy(_snapshot())
    target: object = snapshot
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(RuntimeError, match="pinned request policy is invalid"):
        parse_request_configuration_policy(snapshot)


def test_unsafe_pinned_candidate_group_cannot_route() -> None:
    snapshot = _snapshot()
    organisation = snapshot["organisation"]
    assert isinstance(organisation, dict)
    groups = organisation["candidateGroups"]
    assert isinstance(groups, list)
    groups[0]["candidateGroup"] = "UNSAFE GROUP"
    policy = parse_request_configuration_policy(snapshot)
    team_id = next(
        unit_id
        for unit_id, unit in policy.units.items()
        if unit.kind is OrganisationKind.TEAM
    )
    with pytest.raises(InvalidAction, match="not configured safely"):
        policy.routing_selection(
            parent_id=policy.root_unit_id,
            destination_id=team_id,
            expected_kind=OrganisationKind.TEAM,
            selected_position=1,
        )


async def test_configuration_readiness_rejects_incomplete_runtime() -> None:
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=None)
    assert not await configuration_runtime_is_ready(session)

    registry = MagicMock(active_version_id=uuid4())
    future = MagicMock(
        status=ConfigurationStatus.ACTIVE,
        effective_from=datetime.now(UTC) + timedelta(days=1),
    )
    session.get.side_effect = [registry, future]
    assert not await configuration_runtime_is_ready(session)

    active = MagicMock(
        id=uuid4(),
        status=ConfigurationStatus.ACTIVE,
        effective_from=datetime.now(UTC) - timedelta(days=1),
    )
    session.get.side_effect = [registry, active]
    session.scalar.return_value = None
    assert not await configuration_runtime_is_ready(session)


def test_invalid_workflow_pin_and_tampered_start_fail_closed() -> None:
    assert pinned_workflow_identity({"processId": "", "processVersion": True}) is None
    assert not pinned_start_identity_matches(
        {},
        {},
        instance_process_id=None,
        instance_process_version=None,
        instance_process_checksum=None,
    )
