# RUNBOOK — Déploiement jobtech sur VPS

Mise en production de l'API + dashboard (images publiées par la CI sur GHCR),
PostgreSQL et un reverse-proxy **Caddy** (HTTPS automatique). À exécuter **par toi**
sur le VPS (aucun accès SSH partagé). Cible : une commande.

## Prérequis (VPS)
- Docker + Docker Compose v2 installés.
- Un **domaine** (ex. `jobtech.exemple.com`) dont le DNS (A/AAAA) pointe vers l'IP du VPS.
- Ports **80** et **443** ouverts (Caddy obtient le certificat Let's Encrypt).
- Images GHCR accessibles : publiques (rien à faire) ou `docker login ghcr.io` si privées.

## Étapes

```bash
# 1. Récupérer le kit (le dépôt, ou au minimum le dossier deploy/)
git clone https://github.com/Amiiircmoi/jobtech.git && cd jobtech/deploy

# 2. Configurer (secrets, domaine) — JAMAIS commité
cp .env.prod.example .env
#   éditer .env : DOMAIN, DJANGO_SECRET_KEY (sans '$'), POSTGRES_PASSWORD

# 3. Déployer en UNE commande
./deploy.sh
```

`deploy.sh` enchaîne : pull GHCR → `db` (attente santé) → **ETL one-shot** (crée le
schéma étoile + charge le DWH) → `api` + `caddy` + `etl` (boucle). HTTPS auto sur `${DOMAIN}`.

## Vérification
- `https://${DOMAIN}/` → **dashboard** (salaire médian par pays, distribution).
- `https://${DOMAIN}/api/docs/` → **Swagger**.
- `https://${DOMAIN}/api/v1/salary-stats/?country=FR&skill=python` → indicateurs JSON.

## Exploitation
- Logs : `docker compose -f docker-compose.prod.yml logs -f api`
- Recharger les données : `docker compose -f docker-compose.prod.yml run --rm --entrypoint python etl -m pipeline.run all`
- L'ETL tourne en boucle (intervalle `INTERVAL_HOURS`) ; cible : ordonnancement Dagster.
- Mise à jour : `docker compose -f docker-compose.prod.yml pull && ... up -d` (nouvelles images CI).

## Sécurité
- TLS partout (Caddy) ; `DJANGO_SECURE_SSL_REDIRECT=True` + `DEBUG=False` + `ALLOWED_HOSTS=${DOMAIN}`.
- Secrets dans `deploy/.env` (gitignoré) ; mot de passe Postgres fort ; `SECRET_KEY` sans `$`.
- Sauvegarde : volume `pgdata` (à inclure dans la politique de backup du VPS).
