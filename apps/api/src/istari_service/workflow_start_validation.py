"""Fail-closed validation of stored workflow start identity."""

from __future__ import annotations

from istari_service.configuration_models import RequestConfigurationPin
from istari_service.models import (
    OutboxStatus,
    ServiceRequest,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowOutbox,
)
from istari_service.workflow_start_identity import pinned_start_identity_matches


def reject_invalid_start_identity(
    pin: RequestConfigurationPin | None,
    outbox: WorkflowOutbox,
    request: ServiceRequest,
    instance: WorkflowInstance | None,
) -> bool:
    """Mark invalid new or tampered start state as support-required."""

    if pin is None:
        if instance is not None and instance.legacy_unpinned_identity:
            return False
        message = "Immutable workflow start identity is missing."
    elif pinned_start_identity_matches(
        pin.snapshot,
        outbox.payload,
        instance_process_id=instance.process_id if instance else None,
        instance_process_version=instance.process_version if instance else None,
        instance_process_checksum=instance.process_checksum if instance else None,
    ):
        return False
    else:
        message = "Pinned workflow start identity does not match."
    outbox.status = OutboxStatus.FAILED
    outbox.lease_owner = None
    outbox.last_error = message
    request.workflow_error = "Workflow start needs support."
    if instance is not None:
        instance.status = WorkflowInstanceStatus.ERROR
        instance.last_error = message
    return True
