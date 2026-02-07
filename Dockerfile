# syntax=docker/dockerfile:1

# ============================================================
# Stage 1: Builder
# ============================================================
FROM ghcr.io/astral-sh/uv:0.9-python3.11-bookworm-slim AS builder

WORKDIR /app

# hatch-vcs needs an explicit version when .git metadata is unavailable in build context.
ARG WBV_VERSION=0.0.0+local
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${WBV_VERSION}
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_WEBARENA_VERIFIED=${WBV_VERSION}

# Copy dependency files first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install only production dependencies (no dev, no optional groups)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-group dev

# Copy source code, assets, and README (required by pyproject.toml)
COPY src/ ./src/
COPY assets/ ./assets/
COPY README.md ./

# Install the project itself (non-editable for production)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-group dev --no-editable --compile-bytecode

# ============================================================
# Stage 2: Runtime (minimal)
# ============================================================
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Copy only the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["webarena-verified"]
CMD ["--help"]
