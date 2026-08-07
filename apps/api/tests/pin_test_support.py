"""Immutable workflow pin stub for isolated repository tests."""

from types import SimpleNamespace
from typing import Any


class StaticConfigurationPins:
    async def pin_request(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            snapshot={
                "processId": "service-request-v1",
                "processVersion": 1,
                "processChecksum": "a" * 64,
            },
            organisation_root_id=None,
        )
