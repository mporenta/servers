FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Resolve dependencies first for better layer caching.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev || true

ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-editable

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=uv /app/.venv /app/.venv
COPY --from=uv /app/migrations /app/migrations

ENV PATH="/app/.venv/bin:$PATH" \
    MEMORY_GRAPH_TRANSPORT=http \
    MEMORY_GRAPH_HTTP_HOST=0.0.0.0 \
    MEMORY_GRAPH_HTTP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["mcp-server-memory-graph"]
