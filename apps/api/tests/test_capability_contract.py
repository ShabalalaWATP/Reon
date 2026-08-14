"""Release-capability compatibility and composition boundaries."""

from __future__ import annotations

from fastapi import FastAPI, Request

from istari_service.config import Settings
from istari_service.main import create_app
from istari_service.routers.capabilities import capabilities
from istari_service.schemas.auth import ClientCapabilities


def _legacy_capabilities() -> dict[str, bool]:
    return {
        "my_work": True,
        "notifications": True,
        "configuration": True,
        "products": True,
        "managed_file_uploads": True,
        "planning": True,
        "statistics": True,
    }


def test_additive_capabilities_default_closed_for_legacy_construction() -> None:
    result = ClientCapabilities(**_legacy_capabilities())

    assert result.conversation_reads is False
    assert result.conversation_writes is False
    assert result.context_switching is False
    assert result.model_dump(by_alias=True)["conversationReads"] is False


async def test_capabilities_are_derived_independently_from_registered_routes() -> None:
    settings = Settings()
    complete_app = create_app(settings=settings)
    complete = await capabilities(
        Request({"type": "http", "app": complete_app}),
        object(),  # type: ignore[arg-type]
        settings,
    )

    assert complete.conversation_reads is True
    assert complete.conversation_writes is True
    assert complete.context_switching is True

    partial_app = FastAPI()
    partial = await capabilities(
        Request({"type": "http", "app": partial_app}),
        object(),  # type: ignore[arg-type]
        settings,
    )

    assert partial.conversation_reads is False
    assert partial.conversation_writes is False
    assert partial.context_switching is False


def test_openapi_publishes_independent_camel_case_capabilities() -> None:
    schema = create_app(settings=Settings()).openapi()
    properties = schema["components"]["schemas"]["ClientCapabilities"]["properties"]

    assert properties["conversationReads"]["default"] is False
    assert properties["conversationWrites"]["default"] is False
    assert properties["contextSwitching"]["default"] is False
