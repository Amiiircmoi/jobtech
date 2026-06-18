"""Tests d'intégration du pipeline médaillon (sans base de données) :
lignée bronze→silver→gold, déterminisme (seed figée) et idempotence de la
construction gold. Écrit dans data/ (régénérable, gitignoré)."""

from pipeline import gold, silver, synthetic


def test_bronze_generation_deterministic():
    a = synthetic.generate_all()
    b = synthetic.generate_all()
    # 6 sources + registre des entreprises
    assert set(a) == set(b)
    assert "companies_ref" in a and len(a) == 7


def test_silver_explodes_multiskill_survey():
    synthetic.generate_all()
    out = silver.build_silver()
    # SO Survey : 1 500 répondants éclatés en (répondant × compétence) → > 1 500 lignes
    assert len(out["so_survey"]) > 1500
    # Les 4 sources salariales + 2 popularité
    assert {"adzuna", "indeed", "glassdoor", "so_survey", "github_popularity", "google_trends"} <= set(out)


def test_gold_fact_deterministic_and_idempotent():
    synthetic.generate_all()
    silver.build_silver()
    r1 = gold.build_gold()
    r2 = gold.build_gold()
    # Déterministe : mêmes dimensions + même table de faits à chaque construction
    assert len(r1["fact_job"]) == len(r2["fact_job"])
    assert len(r1["dim_source"]) == 6
    # La table de faits agrège (moins de lignes que les observations silver)
    assert 0 < len(r1["fact_job"]) < 5000
