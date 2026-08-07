"""FastAPI dependencies for explicitly configured product infrastructure."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from istari_service.product_runtime import ProductRuntime


def product_runtime_from_request(request: Request) -> ProductRuntime:
    return cast(ProductRuntime, request.app.state.product_runtime)


ProductRuntimeDependency = Annotated[
    ProductRuntime, Depends(product_runtime_from_request)
]
