FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install API package and dependencies
COPY api/ /app/
RUN pip install --no-cache-dir -e "."

RUN adduser --disabled-password --gecos "" tracelit
USER tracelit

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
