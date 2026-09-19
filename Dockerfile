# The dashboard as one image: FastAPI serves /api, the built React SPA, and —
# when COMPANY_AI_MCP_TOKEN is set — the remote MCP endpoint at /mcp for cloud
# Claude (docs/26), all on a single port. The stdio MCP server (company-ai-mcp)
# is a separate entry point for local use and is NOT run here.
# See .ai/tasks/06-deployment-proposal.md.
#
# Ships the app + synthetic seed ONLY. Real data is never copied in (see
# .dockerignore); it is loaded at runtime into the hosted Aito by the operator.

# ---- stage 1: build the frontend (vite -> src/company_ai/web_dist) ----
FROM node:20-alpine AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# vite outDir is ../src/company_ai/web_dist (see vite.config)
RUN npm run build

# ---- stage 2: python runtime ----
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8770

# deps first (cache layer), then the source. Copy uv.lock and sync --frozen so
# the container installs the EXACT locked versions (e.g. mcp 1.27.2, which has
# mcp.server.fastmcp) — without the lock, `uv sync` re-resolves `mcp>=1.0` fresh
# and can pull an incompatible version, crashing /mcp at startup.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --no-dev --frozen

# the frontend build from stage 1
COPY --from=web /app/src/company_ai/web_dist ./src/company_ai/web_dist
# synthetic seed only (docs are the default library)
COPY data/seed ./data/seed
COPY data/seed_tiny ./data/seed_tiny
COPY docs ./docs
# the advisory roster default + the board/week-prep composer prompts
COPY prompts ./prompts

EXPOSE 8770
# run the already-synced venv binary directly — NOT `uv run` (which would
# re-sync/pull deps at container start). bind 0.0.0.0 and honour $PORT.
CMD ["sh", "-c", "company-ai dashboard --host 0.0.0.0 --port ${PORT:-8770}"]
