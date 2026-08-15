"""Create the transactional search projection for a submitted request."""

from __future__ import annotations

from uuid import UUID

from mist_service.request_search_models import (
    SEARCH_PROJECTION_VERSION,
    RequestSearchDocument,
)
from mist_service.request_search_text import SearchableRequest, build_search_text


def new_search_document(
    request_id: UUID,
    source: SearchableRequest,
) -> RequestSearchDocument:
    text = build_search_text(source)
    return RequestSearchDocument(
        request_id=request_id,
        document_version=SEARCH_PROJECTION_VERSION,
        title_text=text.title,
        question_text=text.question,
        outcome_text=text.outcome,
        context_text=text.context,
        searchable_text=text.all_fields,
    )
