from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import relationship as rel


class UserRole(StrEnum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    REQUESTER = "REQUESTER"
    INTAKE_TRIAGE = "INTAKE_TRIAGE"
    SERVICE_COORDINATION = "SERVICE_COORDINATION"
    OPERATIONS_ALLOCATION = "OPERATIONS_ALLOCATION"
    DELIVERY_TEAM_LEAD = "DELIVERY_TEAM_LEAD"
    DELIVERY_SPECIALIST = "DELIVERY_SPECIALIST"
    QUALITY_RELEASE = "QUALITY_RELEASE"


class RequestStatus(StrEnum):
    ROUTING_PENDING = "ROUTING_PENDING"
    TRIAGE_REVIEW = "TRIAGE_REVIEW"
    INFORMATION_REQUIRED = "INFORMATION_REQUIRED"
    COORDINATION_REVIEW = "COORDINATION_REVIEW"
    ON_HOLD = "ON_HOLD"
    ALLOCATION_REVIEW = "ALLOCATION_REVIEW"
    DELIVERY_PLANNING = "DELIVERY_PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    CUSTOMER_INFORMATION_REQUIRED = "CUSTOMER_INFORMATION_REQUIRED"
    LEAD_REVIEW = "LEAD_REVIEW"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    QUALITY_REVIEW = "QUALITY_REVIEW"
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    COMPLETED = "COMPLETED"
    CLOSED_NOT_PROGRESSED = "CLOSED_NOT_PROGRESSED"
    CANCELLED = "CANCELLED"


class WorkflowInstanceStatus(StrEnum):
    START_PENDING = "START_PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    ERROR = "ERROR"


class WorkflowTaskStatus(StrEnum):
    OPEN = "OPEN"
    CLAIM_PENDING = "CLAIM_PENDING"
    CLAIMED = "CLAIMED"
    COMPLETION_PENDING = "COMPLETION_PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class DeliverableStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    APPROVED = "APPROVED"
    RELEASED = "RELEASED"


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


UTC_TS = DateTime(timezone=True)
UUID_TYPE = Uuid(as_uuid=True)


class IdMixin:
    id: Mapped[UUID] = mapped_column(UUID_TYPE, primary_key=True, default=uuid4)


class CreatedMixin(IdMixin):
    created_at: Mapped[datetime] = mapped_column(UTC_TS, server_default=func.now())


class TimestampMixin(CreatedMixin):
    updated_at: Mapped[datetime] = mapped_column(
        UTC_TS, server_default=func.now(), onupdate=func.now()
    )


def _enum(enum_type: type[StrEnum], name: str) -> SqlEnum:
    return SqlEnum(enum_type, name=name, native_enum=False, create_constraint=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), index=True)
    scope: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    credential_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sessions: Mapped[list[Session]] = rel(back_populates="user")


class Session(CreatedMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    credential_version: Mapped[int] = mapped_column(Integer)
    last_seen_at: Mapped[datetime] = mapped_column(UTC_TS, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(UTC_TS, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    elevated_until: Mapped[datetime | None] = mapped_column(UTC_TS)
    user: Mapped[User] = rel(back_populates="sessions")


class ServiceRequest(TimestampMixin, Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint(
            "(audit_event_count = 0 AND audit_head_hash IS NULL "
            "AND audit_anchor_mac IS NULL) OR "
            "(audit_event_count > 0 AND audit_head_hash IS NOT NULL "
            "AND audit_anchor_mac IS NOT NULL)",
            name="audit_anchor_consistency",
        ),
    )

    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_key: Mapped[UUID | None] = mapped_column(
        UUID_TYPE, unique=True, index=True
    )
    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    service_category: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    desired_outcome: Mapped[str] = mapped_column(Text)
    background_context: Mapped[str] = mapped_column(Text)
    required_by: Mapped[date] = mapped_column(Date)
    required_by_reason: Mapped[str] = mapped_column(Text)
    preferred_deliverable_type: Mapped[str] = mapped_column(String(80))
    success_criteria: Mapped[str] = mapped_column(Text)
    requesting_business_area: Mapped[str] = mapped_column(String(120))
    intended_recipients: Mapped[list[str]] = mapped_column(JSON)
    sensitivity: Mapped[str] = mapped_column(String(20))
    handling_instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "request_status"),
        default=RequestStatus.ROUTING_PENDING,
        server_default=RequestStatus.ROUTING_PENDING.value,
        index=True,
    )
    current_owner: Mapped[str] = mapped_column(
        String(120), default="Intake & Triage Team"
    )
    triage_category: Mapped[str | None] = mapped_column(String(80))
    priority: Mapped[str | None] = mapped_column(String(20))
    assigned_delivery_team: Mapped[str | None] = mapped_column(String(80), index=True)
    assigned_delivery_team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organisation_units.id", ondelete="RESTRICT"), index=True
    )
    assigned_specialist_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    command_group: Mapped[str | None] = mapped_column(String(120))
    ops_group: Mapped[str | None] = mapped_column(String(120))
    team_manager_group: Mapped[str | None] = mapped_column(String(120))
    team_analyst_group: Mapped[str | None] = mapped_column(String(120))
    awaiting_team_staffing: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    required_capabilities: Mapped[list[str] | None] = mapped_column(JSON)
    workflow_error: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    audit_event_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    audit_head_hash: Mapped[str | None] = mapped_column(String(64))
    audit_anchor_mac: Mapped[str | None] = mapped_column(String(64))
    requester: Mapped[User] = rel(foreign_keys=[requester_id])
    assigned_specialist: Mapped[User | None] = rel(
        foreign_keys=[assigned_specialist_id]
    )


class RequestEvent(CreatedMixin, Base):
    __tablename__ = "request_events"
    __table_args__ = (
        UniqueConstraint("event_hash", name="uq_request_events_event_hash"),
        Index("ix_request_events_request_created", "request_id", "created_at"),
    )

    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    prior_status: Mapped[RequestStatus | None] = mapped_column(
        _enum(RequestStatus, "event_prior_status")
    )
    next_status: Mapped[RequestStatus | None] = mapped_column(
        _enum(RequestStatus, "event_next_status")
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))
    actor: Mapped[User | None] = rel(foreign_keys=[actor_user_id])


class WorkflowInstance(TimestampMixin, Base):
    __tablename__ = "workflow_instances"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id"), unique=True, index=True
    )
    process_id: Mapped[str] = mapped_column(String(160))
    process_definition_key: Mapped[str | None] = mapped_column(String(128))
    process_version: Mapped[int | None] = mapped_column(Integer)
    process_checksum: Mapped[str | None] = mapped_column(String(64))
    legacy_unpinned_identity: Mapped[bool] = mapped_column(server_default=false())
    process_instance_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    status: Mapped[WorkflowInstanceStatus] = mapped_column(
        _enum(WorkflowInstanceStatus, "workflow_instance_status"),
        default=WorkflowInstanceStatus.START_PENDING,
    )
    current_element_id: Mapped[str | None] = mapped_column(String(160))
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(UTC_TS)


class WorkflowTask(TimestampMixin, Base):
    __tablename__ = "workflow_tasks"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id"), index=True
    )
    workflow_instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_instances.id")
    )
    task_key: Mapped[str] = mapped_column(String(128), unique=True)
    element_id: Mapped[str] = mapped_column(String(160), index=True)
    name: Mapped[str] = mapped_column(String(160))
    candidate_role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "task_candidate_role")
    )
    expected_status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "task_expected_request_status")
    )
    status: Mapped[WorkflowTaskStatus] = mapped_column(
        _enum(WorkflowTaskStatus, "workflow_task_status"),
        default=WorkflowTaskStatus.OPEN,
        index=True,
    )
    assignee_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    claimed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    completed_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    assignee: Mapped[User | None] = rel(foreign_keys=[assignee_user_id])


class Deliverable(CreatedMixin, Base):
    __tablename__ = "deliverables"
    __table_args__ = (UniqueConstraint("request_id", "version"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_requests.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[DeliverableStatus] = mapped_column(
        _enum(DeliverableStatus, "deliverable_status"),
        default=DeliverableStatus.SUBMITTED,
    )
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    released_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    release_recipients: Mapped[list[str] | None] = mapped_column(JSON)
    approved_at: Mapped[datetime | None] = mapped_column(UTC_TS)
    released_at: Mapped[datetime | None] = mapped_column(UTC_TS)


import istari_service.action_notification_models as _action_models  # noqa: E402, F401
import istari_service.admin_models as _admin_models  # noqa: E402, F401
import istari_service.analytics_evolution_models as _evolution_models  # noqa: E402, F401
import istari_service.analytics_models as _analytics_models  # noqa: E402, F401
import istari_service.board_models as _board_models  # noqa: E402, F401
import istari_service.calendar_models as _calendar_models  # noqa: E402, F401
import istari_service.clarification_models as _clarification_models  # noqa: E402, F401
import istari_service.configuration_models as _configuration_models  # noqa: E402, F401
import istari_service.management_models as _management_models  # noqa: E402, F401
import istari_service.operations_models as _operations_models  # noqa: E402, F401
import istari_service.organisation_models as _organisation_models  # noqa: E402, F401
import istari_service.planning_analytics_models as _planning_models  # noqa: E402, F401
import istari_service.product_models as _product_models  # noqa: E402, F401
import istari_service.related_record_models as _related_record_models  # noqa: E402, F401
import istari_service.request_draft_models as _request_draft_models  # noqa: E402, F401
import istari_service.team_models as _team_models  # noqa: E402, F401
from istari_service.feedback_model import Feedback as Feedback  # noqa: E402
from istari_service.outbox_model import WorkflowOutbox as WorkflowOutbox  # noqa: E402
