from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as rel

from mist_service.model_enums import DeliverableStatus as DeliverableStatus
from mist_service.model_enums import (
    IdentityContext as IdentityContext,
)
from mist_service.model_enums import OutboxStatus as OutboxStatus
from mist_service.model_enums import (
    ProductMode as ProductMode,
)
from mist_service.model_enums import (
    RequestStatus as RequestStatus,
)
from mist_service.model_enums import (
    UserRole as UserRole,
)
from mist_service.model_enums import (
    WorkflowInstanceStatus as WorkflowInstanceStatus,
)
from mist_service.model_enums import (
    WorkflowTaskStatus as WorkflowTaskStatus,
)
from mist_service.orm_base import (
    UTC_TS as UTC_TS,
)
from mist_service.orm_base import (
    UUID_TYPE as UUID_TYPE,
)
from mist_service.orm_base import (
    Base as Base,
)
from mist_service.orm_base import (
    CreatedMixin as CreatedMixin,
)
from mist_service.orm_base import IdMixin as IdMixin
from mist_service.orm_base import (
    TimestampMixin as TimestampMixin,
)
from mist_service.orm_base import (
    _enum as _enum,
)
from mist_service.profile_models import ProfileFieldsMixin


class User(ProfileFieldsMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_updated_id", "updated_at", "id"),)
    username: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    assistance_email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    assistance_email_key_id: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), index=True)
    scope: Mapped[str] = mapped_column(String(120))
    customer_context_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
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
    active_context: Mapped[IdentityContext] = mapped_column(
        _enum(IdentityContext, "identity_context"),
        default=IdentityContext.STAFF,
        server_default=IdentityContext.STAFF.value,
    )
    context_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
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
        Index(
            "ix_service_requests_requester_updated_id",
            "requester_id",
            "updated_at",
            "id",
        ),
        Index("ix_service_requests_updated_id", "updated_at", "id"),
    )

    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    submission_key: Mapped[UUID | None] = mapped_column(
        UUID_TYPE, unique=True, index=True
    )
    requester_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    service_category: Mapped[str] = mapped_column(
        String(80), default="General service request"
    )
    description: Mapped[str] = mapped_column(Text)
    question_to_answer: Mapped[str] = mapped_column(Text)
    desired_outcome: Mapped[str] = mapped_column(Text)
    background_context: Mapped[str] = mapped_column(Text)
    subject_area_or_location: Mapped[str] = mapped_column(Text)
    coverage_start: Mapped[date] = mapped_column(Date)
    coverage_end: Mapped[date] = mapped_column(Date)
    customer_urgency: Mapped[str] = mapped_column(String(20))
    supported_activity_or_decision: Mapped[str] = mapped_column(Text)
    required_by: Mapped[date] = mapped_column(Date)
    required_by_reason: Mapped[str] = mapped_column(Text)
    preferred_deliverable_type: Mapped[str] = mapped_column(String(80))
    product_mode: Mapped[ProductMode] = mapped_column(
        _enum(ProductMode, "request_product_mode"),
        default=ProductMode.LEGACY,
        server_default=ProductMode.LEGACY.value,
    )
    success_criteria: Mapped[str] = mapped_column(Text)
    constraints_or_caveats: Mapped[str] = mapped_column(Text)
    supporting_information: Mapped[str] = mapped_column(Text)
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
    audit_anchor_key_id: Mapped[str | None] = mapped_column(String(64))
    requester: Mapped[User] = rel(foreign_keys=[requester_id])
    assigned_specialist: Mapped[User | None] = rel(
        foreign_keys=[assigned_specialist_id]
    )


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
    __table_args__ = (
        Index(
            "ix_workflow_tasks_role_status_updated_id",
            "candidate_role",
            "status",
            "updated_at",
            "id",
        ),
    )

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


from mist_service.deliverable_model import Deliverable as Deliverable  # noqa: E402
from mist_service.feedback_model import Feedback as Feedback  # noqa: E402
from mist_service.outbox_model import WorkflowOutbox as WorkflowOutbox  # noqa: E402
