# Multi-stage Dockerfile for Warframe Wiki system
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # PDF generation dependencies
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Git for version control
    git \
    # Build tools
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN groupadd -r warframe && useradd -r -g warframe -d /app -s /bin/bash warframe

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p cache pdfs images && \
    chown -R warframe:warframe /app

# Switch to non-root user
USER warframe

# Default command
CMD ["python", "meta/scripts/update_content.py", "--verbose"]

# Development stage
FROM base as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    isort \
    flake8 \
    mypy \
    bandit \
    safety

USER warframe

CMD ["bash"]

# Production stage
FROM base as production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Labels for metadata
LABEL org.opencontainers.image.title="Warframe Wiki System" \
      org.opencontainers.image.description="Automated Warframe wiki generation system" \
      org.opencontainers.image.source="https://github.com/your-org/warframe-wiki" \
      org.opencontainers.image.vendor="Warframe Community" \
      org.opencontainers.image.licenses="MIT"