"""Audience policy values for request event projections."""

from enum import StrEnum


class RequestEventAudience(StrEnum):
    CUSTOMER_AND_STAFF = "CUSTOMER_AND_STAFF"
    STAFF_ONLY = "STAFF_ONLY"
