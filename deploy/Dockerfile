# STAGE 1: Builder
# This stage installs Python dependencies into a virtual environment.
# It will be cached and only re-run when pyproject.toml or uv.lock changes.
FROM python:3.11-slim as builder

# Install uv, the Python package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

WORKDIR /app

# Copy only the dependency definition files
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Set ownership of the app directory while still root
RUN chown -R appuser:appuser /app

# Now, switch to the non-root user
USER appuser

# Install dependencies into a virtual environment using a cache mount for speed
# Note: The cache target is now in the user's home directory.
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=1000,gid=1000 \
    uv venv .venv && \
    uv sync --locked --no-install-project

# STAGE 2: Final Image
# This stage builds the final, lean image for production.
FROM python:3.11-slim

# Install only RUNTIME system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy uv, which is needed for running poe tasks
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user and necessary directories, including the one for supervisor
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser && \
    mkdir -p /app /home/appuser/logs /home/appuser/runtime/supervisor && \
    chown -R appuser:appuser /app /home/appuser

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv

# Copy the rest of the application code
COPY --chown=appuser:appuser . .

# Set environment variables, including adding the venv to the PATH.
# This is done before installing supervisor so the 'pip' command is found.
ENV ATLAN_DAPR_APP_PORT=8000 \
    ATLAN_DAPR_HTTP_PORT=3500 \
    ATLAN_DAPR_GRPC_PORT=50001 \
    ATLAN_DAPR_METRICS_PORT=3100 \
    PATH="/app/.venv/bin:$PATH"

# Switch to root temporarily to install system-wide tools
USER root

# Install Dapr CLI and Supervisor. 'pip' is now in the PATH.
RUN curl -fsSL https://raw.githubusercontent.com/dapr/cli/master/install/install.sh | DAPR_INSTALL_DIR="/usr/local/bin" /bin/bash -s 1.14.1 && \
    pip install --no-cache-dir supervisor

# Copy supervisor config
COPY ./deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Download DAPR components. This needs to be done as the user who will run them.
USER appuser
RUN uv run poe download-components

# Copy and set executable entrypoint
# This section remains owned by root to ensure correct permissions are set.
USER root
COPY --chown=appuser:appuser ./deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && \
    # Fix potential Windows line endings
    sed -i 's/\r$//' /app/entrypoint.sh

# The entrypoint will be run as root, but supervisord.conf will handle privilege dropping.
ENTRYPOINT ["/app/entrypoint.sh"]

