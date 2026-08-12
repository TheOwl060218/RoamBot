FROM node:24-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.13-slim AS backend-builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/src/ ./backend/src/
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels ./backend


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ROAMBOT_DATA_DIR=/data

RUN groupadd --gid 10001 roambot \
    && useradd --uid 10001 --gid roambot --create-home --shell /usr/sbin/nologin roambot \
    && mkdir -p /app/frontend/dist /data \
    && chown -R roambot:roambot /app /data

COPY --from=backend-builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels
COPY --from=frontend-builder --chown=roambot:roambot /build/frontend/dist/ /app/frontend/dist/

USER roambot
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).read()"]
ENTRYPOINT ["python", "-m", "roambot.entrypoint"]
