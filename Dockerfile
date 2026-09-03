FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY integrations ./integrations
COPY scripts ./scripts
COPY servicenow_incident_ingestion.py ./servicenow_incident_ingestion.py
COPY data ./data

RUN mkdir -p /app/data/chroma /app/data/sqlite

EXPOSE 8000

CMD ["sh", "-c", "set -e; if [ \"${RUN_INGESTION_ON_STARTUP:-false}\" = \"true\" ]; then echo 'Starting ServiceNow ingestion'; python backend/rag/servicenow_incident_ingestion.py; fi; echo 'Starting FastAPI'; exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
