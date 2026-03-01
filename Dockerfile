# Stage 1: Build dependencies
FROM python:3.12-slim AS builder
WORKDIR /app

# Install system deps for TA-Lib and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential wget libta-lib-dev && \
  rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim AS runner
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  libta-lib0 curl && \
  rm -rf /var/lib/apt/lists/* && \
  groupadd -r mmcc && useradd -r -g mmcc mmcc

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN chown -R mmcc:mmcc /app
USER mmcc

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
