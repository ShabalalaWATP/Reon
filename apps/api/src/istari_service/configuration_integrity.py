"""Defence-in-depth verification for active configuration approval evidence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from istari_service.configuration_digest import configuration_digest
from istari_service.configuration_models import (
    ConfigurationActivation,
    ConfigurationApproval,
    ConfigurationVersion,
)
from istari_service.configuration_records import stored_utc
from istari_service.configuration_types import (
    ApprovalDecision,
    ConfigurationDraftSpec,
    ConfigurationStatus,
)
from istari_service.models import User, UserRole


async def snapshot_evidence_is_valid(
    session: AsyncSession,
    version_id: UUID,
    specification: ConfigurationDraftSpec,
) -> bool:
    """Confirm activation and independent approval bind the exact snapshot."""
    activation = await session.scalar(
        select(ConfigurationActivation).where(
            ConfigurationActivation.configuration_version_id == version_id
        )
    )
    if activation is None:
        return False
    approval = await session.get(ConfigurationApproval, activation.approval_id)
    version = await session.get(ConfigurationVersion, version_id)
    if (
        approval is None
        or version is None
        or version.status is not ConfigurationStatus.ACTIVE
        or approval.configuration_version_id != version_id
        or approval.decision is not ApprovalDecision.APPROVED
        or approval.reviewed_version + 2 != version.version
        or approval.actor_user_id == version.created_by_user_id
        or activation.activated_by_user_id == version.created_by_user_id
        or activation.superseded_version_id != version.based_on_version_id
        or stored_utc(activation.activated_at) < stored_utc(approval.created_at)
    ):
        return False
    approver = await session.get(User, approval.actor_user_id)
    activator = await session.get(User, activation.activated_by_user_id)
    if not _is_active_platform_administrator(approver) or not (
        _is_active_platform_administrator(activator)
    ):
        return False
    digest = configuration_digest(specification)
    return approval.snapshot_digest == activation.snapshot_digest == digest


def _is_active_platform_administrator(user: User | None) -> bool:
    return bool(
        user is not None and user.is_active and user.role is UserRole.PLATFORM_ADMIN
    )
