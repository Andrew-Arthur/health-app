# ── Stage 1: install dependencies ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: lean runtime image ───────────────────────────────────────────────
FROM python:3.12-slim

# Create a non-root user/group
RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -s /sbin/nologin -M app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY main.py .
COPY app/ ./app/

# Pre-create the data directory with correct ownership
RUN mkdir -p /data && chown app:app /data

USER app

EXPOSE 8080

ENV DB_PATH=/data/health.db \
    PORT=8080

# Bind to all interfaces; port is fixed at 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
