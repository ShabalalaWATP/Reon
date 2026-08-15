"""Framework-free platform classification vocabulary."""

from enum import StrEnum


class PlatformClassification(StrEnum):
    OFFICIAL = "OFFICIAL"
    OFFICIAL_SENSITIVE = "OFFICIAL-SENSITIVE"
    LEVEL_THREE = "SECRET"
    LEVEL_FOUR = "TOP-SECRET"
