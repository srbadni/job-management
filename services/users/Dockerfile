# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.12-slim AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /opt/job-management/services/users
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=build_ca_bundle \
    if [ -r /run/secrets/build_ca_bundle ]; then \
        export SSL_CERT_FILE=/run/secrets/build_ca_bundle; \
    fi; \
    uv sync --locked --no-dev --no-install-project --python 3.12

FROM python:3.12-slim
WORKDIR /opt/job-management/services/users
ENV PATH="/opt/job-management/services/users/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=dependencies /opt/job-management/services/users/.venv .venv
COPY --chmod=755 app ./app
COPY --chmod=755 migrations ./migrations
COPY --chmod=644 alembic.ini main.py database.py ./
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
