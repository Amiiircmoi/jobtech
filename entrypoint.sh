#!/usr/bin/env bash
set -euo pipefail

# Boucle d'ordonnancement « placeholder » du conteneur ETL.
# ⚠️ Remplacée en Phase 3 par un ordonnancement Dagster (assets + planning).
#    Conservée ici pour un déclenchement périodique simple en attendant.

INTERVAL_HOURS="${INTERVAL_HOURS:-24}"
SLEEP_SEC=$(( INTERVAL_HOURS * 3600 ))

echo "▶️ ETL jobtech — pipeline médaillon, intervalle = ${INTERVAL_HOURS}h"

while true; do
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] ▶️ Lancement du pipeline médaillon"
  python -m pipeline.run all \
    && echo "✅ Pipeline OK" \
    || { echo "❌ Échec du pipeline" ; exit 1; }
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] 🎉 Terminé, pause ${INTERVAL_HOURS}h"
  sleep "${SLEEP_SEC}"
done
