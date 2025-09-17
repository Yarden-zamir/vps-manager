FROM ghcr.io/astral-sh/uv:python3.11-alpine AS dependencies

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11-alpine AS runtime

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user
RUN addgroup -g 1001 -S appuser && adduser -S appuser -u 1001

# Set working directory
WORKDIR /app

# Copy virtual environment from dependencies stage
COPY --from=dependencies --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser pyproject.toml ./

# Make sure to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 3000

# Set entry point
ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "src/main.py"]

# Build arguments and environment
ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:3000/health').raise_for_status()"


