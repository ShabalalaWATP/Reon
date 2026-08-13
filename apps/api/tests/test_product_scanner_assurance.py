"""Production scanner-assurance composition and capability boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Request
from pydantic import SecretStr

from istari_service.config import Environment, Settings
from istari_service.domain import Actor
from istari_service.main import create_app
from istari_service.models import UserRole
from istari_service.product_errors import ProductDependencyUnavailable
from istari_service.product_ports import ScannerAssurance
from istari_service.product_runtime import ProductRuntime, local_product_runtime
from istari_service.product_types import ScanDecision, ScanResult
from istari_service.routers.capabilities import capabilities
from istari_service.schemas.products import ManagedArtefactCreate, VersionCommand
from istari_service.services.product_service import ProductService


class ApprovedCdrScanner:
    """Synthetic trusted-boundary adapter used only to verify composition."""

    assurance = ScannerAssurance.APPROVED_SEMANTIC_CDR

    async def scan(
        self,
        chunks: AsyncIterable[bytes],
        **parameters: Any,
    ) -> ScanDecision:
        del chunks, parameters
        return ScanDecision(
            result=ScanResult.FAILED,
            scanner="synthetic-approved-cdr",
            scanner_version="1",
            reason_code="SYNTHETIC_TEST_ONLY",
        )


def production_settings(private_root: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.PROD,
        "database_url": "postgresql+asyncpg://service@db/istari?ssl=verify-full",
        "allow_demo_users": False,
        "session_cookie_secure": True,
        "camunda_auth_mode": "BASIC",
        "camunda_username": "service-client",
        "camunda_password": SecretStr("synthetic-password"),
        "camunda_rest_address": "https://workflow.example.test",
        "web_origin": "https://service.example.test",
        "trusted_origins": frozenset({"https://staff.example.test"}),
        "audit_hmac_key": SecretStr("a" * 32),
        "security_pseudonym_key": SecretStr("s" * 32),
        "product_storage_path": private_root.resolve(),
        "request_embedding_cache_path": (private_root / "model-cache").resolve(),
        "product_allowed_external_domains": frozenset({"products.example.test"}),
        "managed_products_enabled": True,
        "worker_health_required": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_local_inspector_for_managed_uploads(tmp_path: Path) -> None:
    runtime = local_product_runtime(
        tmp_path / "products",
        allowed_external_domains=frozenset({"products.example.test"}),
    )
    assert runtime.scanner_assurance is ScannerAssurance.LOCAL_HEURISTIC
    with pytest.raises(ValueError, match="approved semantic/CDR"):
        create_app(
            settings=production_settings(tmp_path),
            product_runtime=runtime,
        )


async def test_local_composition_keeps_managed_upload_capability(
    tmp_path: Path,
) -> None:
    configured = Settings(
        environment=Environment.LOCAL,
        managed_products_enabled=True,
        product_storage_path=tmp_path / "products",
    )
    app = create_app(settings=configured)
    selected: ProductRuntime = app.state.product_runtime
    assert selected.scanner_assurance is ScannerAssurance.LOCAL_HEURISTIC_AND_MALWARE
    assert selected.managed_file_uploads_enabled is True
    request = Request({"type": "http", "app": app})
    result = await capabilities(request, object(), configured)  # type: ignore[arg-type]
    assert result.managed_file_uploads is True


async def test_external_link_only_mode_conceals_managed_upload_capability(
    tmp_path: Path,
) -> None:
    configured = production_settings(
        tmp_path,
        managed_file_uploads_enabled=False,
    )
    runtime = local_product_runtime(
        tmp_path / "products",
        allowed_external_domains=frozenset({"products.example.test"}),
    )
    app = create_app(
        settings=configured,
        product_runtime=runtime,
    )
    selected: ProductRuntime = app.state.product_runtime
    assert selected.managed_file_uploads_enabled is False
    request = Request({"type": "http", "app": app})
    result = await capabilities(request, object(), configured)  # type: ignore[arg-type]
    assert result.products is True
    assert result.managed_file_uploads is False


def test_production_accepts_an_explicit_approved_cdr_runtime(tmp_path: Path) -> None:
    local = local_product_runtime(tmp_path / "products")
    approved = replace(local, scanner=ApprovedCdrScanner())
    app = create_app(
        settings=production_settings(tmp_path),
        product_runtime=approved,
    )
    selected: ProductRuntime = app.state.product_runtime
    assert selected.approved_semantic_cdr is True
    assert selected.managed_file_uploads_enabled is True


async def test_every_managed_upload_stage_fails_before_repository_access(
    tmp_path: Path,
) -> None:
    repository = AsyncMock()
    runtime = replace(
        local_product_runtime(tmp_path / "products"),
        managed_file_uploads_enabled=False,
    )
    service = ProductService(
        repository,
        runtime.storage,
        runtime.scanner,
        runtime.link_policy,
        AsyncMock(),
        managed_file_uploads_enabled=False,
    )
    actor = Actor(
        id=uuid4(),
        username="synthetic-specialist",
        display_name="Synthetic Specialist",
        role=UserRole.DELIVERY_SPECIALIST,
        scope="Synthetic Team",
    )
    package_id, intent_id = uuid4(), uuid4()
    command = ManagedArtefactCreate(
        expected_version=1,
        label="Synthetic product",
        filename="product.pdf",
        media_type="application/pdf",
        size_bytes=4,
        sha256="a" * 64,
        idempotency_key=uuid4(),
    )
    with pytest.raises(ProductDependencyUnavailable):
        await service.add_managed(actor, package_id, command)
    with pytest.raises(ProductDependencyUnavailable):
        await service.upload_content(
            actor,
            package_id,
            intent_id,
            expected_version=1,
            upload_token="x" * 40,
            chunks=_chunks(),
        )
    with pytest.raises(ProductDependencyUnavailable):
        await service.complete_upload(
            actor,
            package_id,
            intent_id,
            VersionCommand(expected_version=1, idempotency_key=uuid4()),
        )
    assert repository.mock_calls == []


async def _chunks() -> AsyncIterable[bytes]:
    yield b"test"
