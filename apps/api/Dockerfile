# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

FROM ghcr.io/astral-sh/uv:0.12.1@sha256:cf4eedcaa81655197f625739489effcbe71b61ceb1506f332c3facae5deceded AS uv

FROM ubuntu:24.04@sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea AS python-runtime

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 python3.12 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.12 /usr/local/bin/python \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

FROM python-runtime AS build

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    REQUEST_EMBEDDING_CACHE_PATH=/app/.model-cache

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    apt-get update \
    && apt-get install --no-install-recommends -y python3.12-venv \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen --no-install-project --no-group dev --no-group test

# FastEmbed resolves a Hugging Face model alias during the image build. Verify the
# resolved revision and every runtime artefact before the network is removed.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/app/.model-cache')" \
    && test "$(cat /app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/refs/main)" = "52398278842ec682c6f32300af41344b1c0b0bb2" \
    && printf '%s  %s\n' \
        'd241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66' '/app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/blobs/688882a79f44442ddc1f60d70334a7ff5df0fb47' \
        '13582bcf2effc85b7bf3d3f5532e686bc1c9ce86bb009d10f0ec33cbe92299dd' '/app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/blobs/0d7726d0cdccb62ee17c03bd1595cff07199b8f8' \
        '0b29c7bfc889e53b36d9dd3e686dd4300f6525110eaa98c76a5dafceb2029f53' '/app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/blobs/75305659f7795d4549f0e23688b52fa20a32f925' \
        '51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431' '/app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/blobs/51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431' \
        '5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a' '/app/.model-cache/models--qdrant--bge-small-en-v1.5-onnx-q/blobs/9bbecc17cabbcbd3112c14d6982b51403b264bfa' \
        | sha256sum --check --strict -

COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY apps/api/src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-group dev --no-group test

FROM python-runtime AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    REQUEST_EMBEDDING_CACHE_PATH=/app/.model-cache

WORKDIR /app

COPY --from=build --chown=10001:10001 /app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "mist_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
