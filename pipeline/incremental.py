"""Micro-batch incrémental.

Au lieu de tout reconstruire (full-refresh batch), on n'ingère que les offres
« fraîches » d'une **fenêtre** (une journée), depuis un **watermark**, et on les
**UPSERT** dans le DWH sans toucher l'historique. Honnête : pas de streaming
sub-seconde (les sources se rafraîchissent ~quotidiennement → la fenêtre est la
journée). Orchestré par un asset Dagster **partitionné par jour** + planning
(voir orchestration/definitions.py).
"""

import json
import random
from datetime import date, datetime, timedelta

import pandas as pd
from faker import Faker

from . import config, gold, lake, load_dw, quality, sources

WATERMARK_PATH = config.DATA_DIR / "watermark.json"


def read_watermark() -> date:
    if WATERMARK_PATH.exists():
        return date.fromisoformat(json.loads(WATERMARK_PATH.read_text())["last_date"])
    return datetime.strptime(config.AS_OF_DATE, "%Y-%m-%d").date()


def write_watermark(d: date) -> None:
    WATERMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATERMARK_PATH.write_text(json.dumps({"last_date": d.isoformat()}))


def generate_fresh_rows(batch_date: date, n: int = 40) -> pd.DataFrame:
    """Offres fraîches du jour (schéma silver), déterministes par date (seed dérivée)."""
    seed = config.RANDOM_SEED + batch_date.toordinal()
    rng = random.Random(seed)
    fake = Faker("en_US")
    Faker.seed(seed)
    rows = []
    for _ in range(n):
        c = rng.choice(config.COUNTRIES)
        s = rng.choice(config.SKILLS)
        _, exp = rng.choice(sources.EXPERIENCE_LEVELS)
        eur = round(config.BASE_SALARY_EUR * c["salary_index"] * s["premium"] * exp * rng.uniform(0.85, 1.20), 2)
        rows.append({
            "source": "adzuna",
            "date_posted": batch_date.isoformat(),
            "country_iso2": c["iso2"],
            "skill": s["label"],
            "company": fake.company(),
            "salary_eur": eur,
            "min_salary_eur": round(eur * 0.9, 2),
            "max_salary_eur": round(eur * 1.1, 2),
        })
    return pd.DataFrame(rows, columns=sources.SALARY_COLS)


def _build_dims(fresh: pd.DataFrame) -> dict:
    companies = pd.DataFrame({"company_name": sorted(fresh["company"].unique())})
    companies["workforce_size"] = None
    companies["sector"] = None
    return {
        "dim_date": gold.build_dim_date(fresh["date_posted"]),
        "dim_country": gold.build_dim_country(),
        "dim_skill": gold.build_dim_skill(),
        "dim_source": gold.build_dim_source(),
        "dim_company": companies,
    }


def run_micro_batch(batch_date: date | None = None) -> dict:
    """Ingère + charge un lot incrémental pour une journée. Idempotent (UPSERT)."""
    if batch_date is None:
        batch_date = read_watermark() + timedelta(days=1)

    fresh = generate_fresh_rows(batch_date)
    quality.validate(fresh, quality.SILVER_SALARY, f"increment:{batch_date}")
    # Lineage : on matérialise le lot en silver (couche partitionnée)
    lake.write_parquet("silver", f"_increments/inc_{batch_date.isoformat()}", fresh, source="increment")

    fact = gold.build_fact(fresh)
    quality.validate(fact, quality.GOLD_FACT, f"increment-fact:{batch_date}")

    counts = load_dw.load_increment(_build_dims(fresh), fact)
    write_watermark(batch_date)
    print(f"  micro-batch {batch_date}: +{len(fresh)} offres → fact_job={counts['fact_job']}")
    return {"batch_date": batch_date.isoformat(), "rows": len(fresh), **counts}


if __name__ == "__main__":
    run_micro_batch()
