"""Public platform marking and elevated mutation contracts."""

from datetime import datetime

from pydantic import Field

from istari_service.platform_security_models import PlatformClassification
from istari_service.schemas.common import ApiModel, StrictApiModel


class PlatformClassificationView(ApiModel):
    classification: PlatformClassification
    version: int
    updated_at: datetime


class PlatformClassificationUpdate(StrictApiModel):
    classification: PlatformClassification
    expected_version: int = Field(ge=1)
