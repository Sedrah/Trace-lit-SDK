FROM python:3.11-slim

WORKDIR /app

# Install system deps needed for confluent-kafka and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc librdkafka-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy SDK first (ingestion depends on it)
COPY sdk/python/ /sdk/python/
RUN pip install --no-cache-dir /sdk/python/

# Copy ingestion package
COPY ingestion/ /app/
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir -e "."

# Non-root user for security
RUN adduser --disabled-password --gecos "" tracelit
USER tracelit

CMD ["python", "-m", "pipeline.main"]
