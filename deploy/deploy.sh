#!/usr/bin/env bash
# Déploiement jobtech en UNE commande (à lancer sur le VPS depuis deploy/).
#   1) DB up + attente santé  2) ETL one-shot (crée le schéma + charge le DWH)
#   3) API + Caddy (TLS auto)  4) ETL en boucle d'ingestion
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "❌ deploy/.env manquant (cp .env.prod.example .env puis renseigner)"; exit 1; }

CMD="docker compose -f docker-compose.prod.yml"

echo "▶ Pull des images GHCR"
$CMD pull

echo "▶ Base de données"
$CMD up -d db
until $CMD exec -T db pg_isready -U "$(grep POSTGRES_USER .env | cut -d= -f2)" >/dev/null 2>&1; do sleep 2; done

echo "▶ Chargement initial du DWH (ETL one-shot)"
$CMD run --rm --entrypoint python etl -m pipeline.run all

echo "▶ API + reverse-proxy TLS (Caddy)"
$CMD up -d api caddy etl

echo "✅ Déployé. Dashboard : https://$(grep DOMAIN .env | cut -d= -f2)/  ·  API docs : /api/docs/"
