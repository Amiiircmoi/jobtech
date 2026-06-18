# ── Image ETL / pipeline médaillon jobtech ────────────────────────────────
# Exécute le pipeline bronze → silver → gold → load (PostgreSQL).
# La config (DATABASE_URL, etc.) est injectée par variables d'environnement.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    INTERVAL_HOURS=24

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ ./pipeline/
COPY sql/ ./sql/
COPY config/ ./config/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
