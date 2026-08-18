"""Shared product lifecycle records and request-event persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mist_service.models import ServiceRequest
from mist_service.product_models import ProductPackage
from mist_service.repositories.event_store import append_request_event
from mist_service.request_event_audience import RequestEventAudience


class ProductLifecycleEventMixin:
    session: AsyncSession

    async def _event(
        self,
        package: ProductPackage,
        event_type: str,
        message: str,
        actor_id: UUID | None = None,
    ) -> None:
        request = await self.session.get(ServiceRequest, package.request_id)
        if request:
            await append_request_event(
                self.session,
                request_id=request.id,
                actor_id=actor_id or package.author_user_id,
                event_type=event_type,
                message=message,
                prior_status=request.status,
                next_status=request.status,
                audience=(
                    RequestEventAudience.CUSTOMER_AND_STAFF
                    if event_type
                    in {
                        "PRODUCT_DISSEMINATED",
                        "PRODUCT_ACCEPTED",
                        "PRODUCT_WITHDRAWN",
                        "PRODUCT_REPLACED",
                    }
                    else RequestEventAudience.STAFF_ONLY
                ),
                details={
                    "packageId": str(package.id),
                    "packageVersion": package.package_version,
                },
            )
