"""Stable application errors translated to HTTP at the outer boundary."""

from __future__ import annotations


class ServiceError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    public_message = "The request could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)
        self.message = message or self.public_message


class AuthenticationFailed(ServiceError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"
    public_message = "Unable to sign in with those credentials."


class AuthenticationRateLimited(ServiceError):
    status_code = 429
    code = "AUTHENTICATION_RATE_LIMITED"
    public_message = "Sign-in is temporarily unavailable. Try again shortly."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__()
        self.retry_after_seconds = max(1, min(3_600, retry_after_seconds))

    @property
    def response_headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after_seconds)}


class AuthenticationUnavailable(ServiceError):
    status_code = 503
    code = "AUTHENTICATION_UNAVAILABLE"
    public_message = "Sign-in is temporarily unavailable. Try again shortly."


class SessionRequired(ServiceError):
    status_code = 401
    code = "SESSION_REQUIRED"
    public_message = "Sign in is required."


class CsrfFailed(ServiceError):
    status_code = 403
    code = "CSRF_FAILED"
    public_message = "The request could not be verified."


class IdentityContextDenied(ServiceError):
    status_code = 403
    code = "IDENTITY_CONTEXT_DENIED"
    public_message = "That account context is not available."


class ObjectNotFound(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class InvalidAction(ServiceError):
    status_code = 409
    code = "INVALID_ACTION"
    public_message = "That action is not valid for the current stage."


class AlreadyClaimed(ServiceError):
    status_code = 409
    code = "ALREADY_CLAIMED"
    public_message = "This work item has already been claimed."


class FeedbackUnavailable(ServiceError):
    status_code = 409
    code = "FEEDBACK_UNAVAILABLE"
    public_message = "Feedback is available once, after successful completion."


class WorkflowUnavailable(ServiceError):
    status_code = 503
    code = "WORKFLOW_UNAVAILABLE"
    public_message = (
        "The action was recorded and will be retried. Refresh to check its status."
    )


class WorkflowActionPending(ServiceError):
    status_code = 409
    code = "WORKFLOW_ACTION_PENDING"
    public_message = "This action is already recorded and is being processed."


class AdministrationAccessDenied(ServiceError):
    status_code = 403
    code = "ADMINISTRATION_ACCESS_DENIED"
    public_message = "Platform administration access is required."


class StepUpRequired(ServiceError):
    status_code = 403
    code = "STEP_UP_REQUIRED"
    public_message = "Confirm your password before making this sensitive change."


class AdministrationUnavailable(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class InvalidAdministrationChange(ServiceError):
    status_code = 409
    code = "INVALID_ADMINISTRATION_CHANGE"
    public_message = "That administration change cannot be applied."


class StaleVersion(ServiceError):
    status_code = 409
    code = "STALE_VERSION"
    public_message = "This record has changed. Refresh and try again."


class StatisticsQueryInvalid(ServiceError):
    status_code = 422
    code = "INVALID_STATISTICS_QUERY"
    public_message = "The statistics filters are invalid."


class InvalidRosterChange(ServiceError):
    status_code = 409
    code = "INVALID_ROSTER_CHANGE"
    public_message = "That roster change cannot be applied."


class TeamWorkspaceNotFound(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class CalendarItemNotFound(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class InvalidCalendarChange(ServiceError):
    status_code = 409
    code = "INVALID_CALENDAR_CHANGE"
    public_message = "That calendar change cannot be applied."


class BoardItemNotFound(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class InvalidBoardChange(ServiceError):
    status_code = 409
    code = "INVALID_BOARD_CHANGE"
    public_message = "That board or planning change cannot be applied."
