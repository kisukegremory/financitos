# syntax=docker/dockerfile:1

# --- UI (Svelte) ---
FROM node:22-alpine AS web
WORKDIR /web
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=bind,source=web/package.json,target=package.json \
    --mount=type=bind,source=web/package-lock.json,target=package-lock.json \
    npm ci
COPY web ./
RUN npm run build

# --- Python deps ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# --- Runtime ---
FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=web --chown=app:app /web/dist /app/web/dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 WEB_DIST=/app/web/dist
RUN mkdir -p /app/data && chown app:app /app/data
USER app
ENTRYPOINT ["home"]
