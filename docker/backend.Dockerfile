FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend /app/backend
COPY config.example.yaml /app/config.yaml
COPY extensions_config.json /app/extensions_config.json
COPY skills/public /app/skills/public
ENV T2I_PROJECT_ROOT=/app T2I_STATE_ROOT=/data/state T2I_ASSET_ROOT=/data/assets
RUN uv sync --project backend --frozen --no-dev
WORKDIR /app/backend
CMD ["/app/backend/.venv/bin/uvicorn","src.gateway.app:app","--host","0.0.0.0","--port","8001"]
