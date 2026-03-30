# ============================================================
# Stage 1 — Builder
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a prefix for easy copy
COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2 — Runtime
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# Run migrations then start the app
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
