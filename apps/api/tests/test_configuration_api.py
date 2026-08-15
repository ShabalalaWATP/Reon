"""HTTP contract and step-up boundary for configuration administration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from conftest import ApiHarness
from mist_service.configuration_models import ApprovedWorkflowDefinition
from mist_service.configuration_policy import WORKFLOW_COMPATIBILITY_KEY


@pytest.mark.asyncio
async def test_configuration_api_requires_step_up_and_independent_admin(
    api_harness: ApiHarness,
) -> None:
    harness = api_harness
    await harness.login("admin1")
    versions = await harness.client.get("/api/v1/admin/configuration/versions")
    assert versions.status_code == 200
    assert len(versions.json()["items"]) == 1
    active_response = await harness.client.get("/api/v1/admin/configuration/active")
    assert active_response.status_code == 200
    active = active_response.json()
    workflow_id = await _add_approved_workflow(harness)
    draft = _draft_payload(active, workflow_id)

    denied = await harness.client.post(
        "/api/v1/admin/configuration/versions",
        json=draft,
        headers=harness.mutation_headers(),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    await harness.elevate()
    created_response = await harness.client.post(
        "/api/v1/admin/configuration/versions",
        json=draft,
        headers=harness.mutation_headers(),
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert created["status"] == "DRAFT"

    validated = await _action(
        harness,
        created["id"],
        "validate",
        {"expectedVersion": created["version"]},
    )
    assert validated["status"] == "VALIDATED", validated["findings"]
    submitted = await _action(
        harness,
        created["id"],
        "submit",
        {
            "expectedVersion": validated["version"],
            "reason": "Submit the exact version for independent approval.",
        },
    )
    self_approval = await harness.client.post(
        f"/api/v1/admin/configuration/versions/{created['id']}/approve",
        json={
            "expectedVersion": submitted["version"],
            "reason": "The creator must not approve their own configuration.",
        },
        headers=harness.mutation_headers(),
    )
    assert self_approval.status_code == 409

    await harness.login("admin73")
    await harness.elevate()
    approved = await _action(
        harness,
        created["id"],
        "approve",
        {
            "expectedVersion": submitted["version"],
            "reason": "Independent review confirms this bounded configuration.",
        },
    )
    activated = await _action(
        harness,
        created["id"],
        "activate",
        {
            "expectedVersion": approved["version"],
            "reason": "Activate the approved version for new requests only.",
        },
    )
    assert activated["status"] == "ACTIVE"

    current = await harness.client.get("/api/v1/admin/configuration/active")
    assert current.status_code == 200 and current.json()["id"] == created["id"]
    preview = await harness.client.get(
        f"/api/v1/admin/configuration/versions/{created['id']}/preview"
    )
    assert preview.status_code == 200
    assert any(
        item["type"] == "WORKFLOW_AFFECTED" for item in preview.json()["changes"]
    )
    organisation = await harness.client.get(
        f"/api/v1/admin/configuration/versions/{created['id']}/organisation",
        params={"at": activated["effectiveFrom"]},
    )
    assert organisation.status_code == 200
    assert organisation.json()["units"]

    await harness.login("admin2")
    forbidden = await harness.client.get("/api/v1/admin/configuration/versions")
    assert forbidden.status_code == 403


async def _add_approved_workflow(harness: ApiHarness) -> str:
    approver_id = await harness.user_id("admin73")
    async with harness.sessions() as session, session.begin():
        workflow = ApprovedWorkflowDefinition(
            process_id="service-request-v2",
            process_definition_key="api-definition-v2",
            process_version=2,
            deployment_key="api-deployment-v2",
            compatibility_key=WORKFLOW_COMPATIBILITY_KEY,
            checksum="b" * 64,
            approved_by_user_id=approver_id,
            approved_at=datetime.now(UTC),
            is_available=True,
        )
        session.add(workflow)
        await session.flush()
        return str(workflow.id)


def _draft_payload(active: dict[str, object], workflow_id: str) -> dict[str, object]:
    template = dict(cast(dict[str, object], active["workflowTemplate"]))
    template["workflowDefinitionId"] = workflow_id
    effective_from = datetime.now(UTC).isoformat()
    units = [
        {**item, "effectiveFrom": effective_from}
        for item in cast(list[dict[str, object]], active["units"])
    ]
    edges = [
        {**item, "effectiveFrom": effective_from}
        for item in cast(list[dict[str, object]], active["edges"])
    ]
    return {
        "label": "API configuration evolution",
        "effectiveFrom": effective_from,
        "basedOnVersionId": active["id"],
        "units": units,
        "edges": edges,
        "candidateGroups": active["candidateGroups"],
        "workflowTemplate": template,
    }


async def _action(
    harness: ApiHarness,
    version_id: str,
    action: str,
    payload: dict[str, object],
) -> dict[str, object]:
    response = await harness.client.post(
        f"/api/v1/admin/configuration/versions/{version_id}/{action}",
        json=payload,
        headers=harness.mutation_headers(),
    )
    assert response.status_code == 200, response.text
    return response.json()
