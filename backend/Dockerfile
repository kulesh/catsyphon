# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

RUN pip install uv

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Copy source code, then install the project itself
COPY src/ src/
COPY alembic.ini ./
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed venv and source
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
