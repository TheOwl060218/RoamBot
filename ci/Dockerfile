FROM node:24-bookworm-slim AS node-runtime


FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_RETRIES=10 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROAMBOT_PROVIDER_MODE=mock \
    ROAMBOT_DEMO_MODE=true \
    NO_PROXY=127.0.0.1,localhost

COPY --from=node-runtime /usr/local/bin/ /usr/local/bin/
COPY --from=node-runtime /usr/local/lib/node_modules/ /usr/local/lib/node_modules/

WORKDIR /workspace

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\n' \
        > /etc/apt/apt.conf.d/80-roambot-retries \
    && cd frontend \
    && npm ci \
    && for attempt in 1 2 3; do \
        if npx playwright install --with-deps chromium; then exit 0; fi; \
        if [ "$attempt" = 3 ]; then exit 1; fi; \
        sleep $((attempt * 10)); \
    done

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/src/ ./backend/src/
RUN python -m venv .venv \
    && for attempt in 1 2 3; do \
        if .venv/bin/python -m pip install --no-cache-dir -e "./backend[dev]"; then exit 0; fi; \
        if [ "$attempt" = 3 ]; then exit 1; fi; \
        sleep $((attempt * 10)); \
    done

COPY . .
RUN chmod +x scripts/test.sh

CMD ["./scripts/test.sh"]
