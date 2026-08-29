FROM python:3.12-slim

LABEL maintainer="LeronX Team"
LABEL description="Open-Source AI Video Generation Pipeline"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LERONX_GPU=false \
    LERONX_CODEC=h265

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Files required during Python package installation
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install project and development/test dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir ".[dev]" pytest-cov

# Test and example files
COPY tests/ ./tests/
COPY examples/ ./examples/

# This repository currently behaves as a Python library/test project,
# not as a persistent web API service.
CMD ["python", "-m", "pytest", "tests/", "-v", "--cov=leronx", "--cov-report=term-missing"]
