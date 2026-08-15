"""Local-only request embedding boundary."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from fastembed import TextEmbedding

from mist_service.request_search_models import EMBEDDING_DIMENSIONS


class RequestEmbeddingProvider(Protocol):
    model_name: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedRequestEmbeddingProvider:
    """Lazily run the bundled ONNX model away from the event loop."""

    def __init__(
        self,
        *,
        model_name: str,
        cache_path: Path,
        threads: int,
    ) -> None:
        self.model_name = model_name
        self._cache_path = cache_path
        self._threads = threads
        self._model: TextEmbedding | None = None
        self._lock = asyncio.Lock()

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        async with self._lock:
            vectors = await asyncio.to_thread(self._embed_sync, tuple(texts))
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS or not all(
                math.isfinite(value) for value in vector
            ):
                raise ValueError("embedding model returned an invalid vector")
        return vectors

    def _embed_sync(self, texts: Sequence[str]) -> list[list[float]]:
        if self._model is None:
            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(self._cache_path),
                threads=self._threads,
                local_files_only=True,
            )
        return [vector.astype(float).tolist() for vector in self._model.embed(texts)]
