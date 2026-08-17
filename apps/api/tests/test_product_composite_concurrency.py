"""Composite product scanning concurrency and cancellation regressions."""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from mist_service.product_clamav import CompositeDocumentScanner
from mist_service.product_types import ScanDecision, ScanResult

PDF_MEDIA = "application/pdf"
BODY = b"%PDF-1.7\nSynthetic content"


async def _chunks(body: bytes) -> AsyncIterator[bytes]:
    yield body


async def _run(scanner: CompositeDocumentScanner) -> ScanDecision:
    return await scanner.scan(
        _chunks(BODY),
        filename="report.pdf",
        declared_media_type=PDF_MEDIA,
        expected_size=len(BODY),
        expected_checksum=hashlib.sha256(BODY).hexdigest(),
    )


async def test_composite_bounds_outer_spooling_and_rejects_zero_slots() -> None:
    active = maximum = 0
    clean = ScanDecision(ScanResult.CLEAN, "test-scanner", "1")
    delegate = SimpleNamespace(scan=AsyncMock(return_value=clean))

    class ProbeComposite(CompositeDocumentScanner):
        async def _scan(self, *args, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.01)
                return await super()._scan(*args, **kwargs)
            finally:
                active -= 1

    scanner = ProbeComposite(delegate, delegate, maximum_concurrent_scans=2)
    results = await asyncio.gather(*(_run(scanner) for _ in range(6)))
    assert all(result.result is ScanResult.CLEAN for result in results)
    assert maximum == 2
    with pytest.raises(ValueError, match="must be positive"):
        CompositeDocumentScanner(delegate, delegate, maximum_concurrent_scans=0)


async def test_composite_cancellation_releases_its_outer_scan_slot() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    clean = ScanDecision(ScanResult.CLEAN, "test-scanner", "1")

    async def scan(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        entered.set()
        if calls == 1:
            await release.wait()
        return clean

    delegate = SimpleNamespace(scan=scan)
    scanner = CompositeDocumentScanner(
        delegate,
        delegate,
        maximum_concurrent_scans=1,
    )
    first = asyncio.create_task(_run(scanner))
    await entered.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    second = await asyncio.wait_for(_run(scanner), timeout=1)
    assert second.result is ScanResult.CLEAN
