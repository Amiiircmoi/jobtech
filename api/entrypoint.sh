#!/usr/bin/env bash
set -euo pipefail

# Migrations Django (tables internes : auth, sessions, JWT…) — le schéma étoile
# du DW, lui, appartient au pipeline et n'est pas migré (modèles managed=False).
python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null 2>&1 || true

# Serveur WSGI de production
exec gunicorn jobtech_api.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
