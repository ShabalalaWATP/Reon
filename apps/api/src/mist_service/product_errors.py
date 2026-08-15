"""Stable failures for private managed-product operations."""

from mist_service.errors import ServiceError


class ProductNotFound(ServiceError):
    status_code = 404
    code = "NOT_FOUND"
    public_message = "The requested item was not found."


class ProductConflict(ServiceError):
    status_code = 409
    code = "PRODUCT_CONFLICT"
    public_message = "That product action is not valid for the current version."


class ProductValidationFailed(ServiceError):
    status_code = 422
    code = "PRODUCT_VALIDATION_FAILED"
    public_message = "The product artefact did not pass validation."


class ProductDependencyUnavailable(ServiceError):
    status_code = 503
    code = "PRODUCT_DEPENDENCY_UNAVAILABLE"
    public_message = "The private product service is temporarily unavailable."
