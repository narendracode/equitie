FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app

# Copy workspace manifests first — layer-cache friendly
COPY pyproject.toml ./
COPY packages/common/pyproject.toml packages/common/pyproject.toml
COPY packages/ai/pyproject.toml     packages/ai/pyproject.toml
COPY packages/api/pyproject.toml    packages/api/pyproject.toml

# Copy source trees
COPY packages/common/src packages/common/src
COPY packages/ai/src     packages/ai/src
COPY packages/api/src    packages/api/src

# Copy alembic alongside the common package
COPY packages/common/alembic     packages/common/alembic
COPY packages/common/alembic.ini packages/common/alembic.ini

# Install all workspace packages (creates /app/.venv)
RUN uv sync --all-packages --no-dev

# Make venv binaries available without full path
ENV PATH="/app/.venv/bin:$PATH"

COPY packages/api/entrypoint.sh /entrypoint.sh
COPY packages/api/worker_entrypoint.sh /app/packages/api/worker_entrypoint.sh
RUN chmod +x /entrypoint.sh /app/packages/api/worker_entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
