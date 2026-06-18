"""Test du micro-batch incrémental : un nouveau lot s'AJOUTE (UPSERT) sans
écraser l'historique, et rejouer la même fenêtre est idempotent.
Assertions par DATE (robustes à l'état antérieur du DWH partagé).
Nécessite PostgreSQL (service CI / Postgres local)."""

from datetime import date

import psycopg

from pipeline import config, incremental


def _count_for(d: date) -> int:
    with psycopg.connect(config.DATABASE_URL) as conn:
        row = conn.execute("SELECT count(*) FROM fact_job WHERE date_key = %s", (d.isoformat(),)).fetchone()
        return row[0]


def test_micro_batch_appends_and_is_idempotent():
    d1, d2 = date(2099, 1, 1), date(2099, 1, 2)

    incremental.run_micro_batch(d1)
    n1 = _count_for(d1)
    assert n1 > 0  # lot ingéré

    incremental.run_micro_batch(d1)  # rejeu de la même fenêtre
    assert _count_for(d1) == n1  # idempotent : aucun doublon

    incremental.run_micro_batch(d2)  # nouvelle fenêtre
    assert _count_for(d2) > 0  # ajoutée
    assert _count_for(d1) == n1  # historique préservé (pas de full-refresh)
