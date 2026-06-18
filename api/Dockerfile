# ── Image API Django REST (servie par gunicorn) ───────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dépendances (contexte de build = racine du dépôt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'API
COPY api/ ./api/

WORKDIR /app/api
RUN chmod +x entrypoint.sh
EXPOSE 8000

# Migrations Django puis serveur WSGI de production
ENTRYPOINT ["./entrypoint.sh"]
