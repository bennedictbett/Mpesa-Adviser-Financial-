#  M-Pesa Financial Advisor — Dockerfile 
# Multi-stage build:
#   Stage 1 (builder) — installs dependencies
#   Stage 2 (runtime) — lean production image

#  Stage 1: Builder 
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker cache — only reinstalls if requirements change)
COPY requirements.txt .

# Install all Python dependencies into a separate directory
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Runtime 
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY src/       ./src/
COPY app/       ./app/
COPY config/    ./config/
COPY data/raw/  ./data/raw/

# Create chroma_db directory — will be populated at runtime
RUN mkdir -p data/chroma_db

# Never run as root in production
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Health check — Docker will call this every 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Start the FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]