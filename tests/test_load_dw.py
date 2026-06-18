"""Test d'intégration du chargement DWH (PostgreSQL) : idempotence du full-refresh.
Nécessite une base PostgreSQL accessible via DATABASE_URL (service CI / Postgres local)."""

from pipeline import gold, load_dw, silver, synthetic


def test_load_is_idempotent():
    synthetic.generate_all()
    silver.build_silver()
    gold.build_gold()
    counts_1 = load_dw.load()
    counts_2 = load_dw.load()
    # Rejouer le chargement donne exactement le même état (full-refresh idempotent)
    assert counts_1 == counts_2
    assert counts_1["fact_job"] > 0
    assert counts_1["d_source"] == 6
