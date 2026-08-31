# Quill image — shared by api, worker, browser services.
# Multi-stage: build the frontend, then the Python runtime with Playwright.

FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy AS runtime
# ^ ships Chromium + Xvfb deps; playwright pip pinned to match.
RUN apt-get update && apt-get install -y --no-install-recommends \
      x11vnc novnc websockify xvfb tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && python -m playwright install chromium

COPY backend/ /app/backend/
COPY selectors/ /app/selectors/
COPY fixtures/ /app/fixtures/
COPY docker/ /app/docker/
COPY --from=frontend /fe/dist /app/frontend/dist
RUN chmod +x /app/docker/browser-entrypoint.sh

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
ENTRYPOINT ["tini", "--"]
