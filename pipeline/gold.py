"""Couche GOLD : silver → tables du schéma en étoile (dimensions + faits) en Parquet.

La table de faits agrège les observations salariales des 4 sources « salaire »
au grain date × pays × compétence × entreprise × source (mesures : avg/min/max
salaire EUR, job_count). Les dimensions sont dédoublonnées et complètes.
C'est le « cube » multidimensionnel exposé ensuite par l'API.
"""

import pandas as pd

from . import config, lake, quality, sources

UNKNOWN_COMPANY = "Unknown"
FACT_GRAIN = ["date_posted", "country_iso2", "skill", "company", "source"]


def _silver(name: str) -> pd.DataFrame:
    return pd.read_parquet(config.SILVER_DIR / f"{name}.parquet")


def _salary_frame() -> pd.DataFrame:
    parts = [_silver(s) for s in sources.salary_source_names()]
    df = pd.concat(parts, ignore_index=True)
    df["company"] = df["company"].fillna(UNKNOWN_COMPANY).replace("", UNKNOWN_COMPANY)
    return df


# ── Dimensions ─────────────────────────────────────────────────────────────


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    d = pd.to_datetime(pd.Series(dates).dropna().unique())
    df = pd.DataFrame({"_d": d})
    df["date_key"] = df["_d"].dt.date.astype("string")
    df["day"] = df["_d"].dt.day
    df["month"] = df["_d"].dt.month
    df["quarter"] = df["_d"].dt.quarter
    df["year"] = df["_d"].dt.year
    df["day_week"] = df["_d"].dt.weekday
    return df.drop(columns="_d").sort_values("date_key").reset_index(drop=True)


def build_dim_country() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "iso2": c["iso2"],
                "country_name": c["name"],
                "region": c["region"],
                "monnaie_iso3": c["currency"],
            }
            for c in config.COUNTRIES
        ]
    )


def build_dim_skill() -> pd.DataFrame:
    return pd.DataFrame(
        [{"tech_label": s["label"], "skill_group": s["group"]} for s in config.SKILLS]
    )


def build_dim_source() -> pd.DataFrame:
    return pd.DataFrame([{"source_name": s} for s in sources.all_source_names()])


def build_dim_company(salary: pd.DataFrame) -> pd.DataFrame:
    appearing = pd.DataFrame({"company_name": sorted(salary["company"].dropna().unique())})
    ref = pd.read_csv(config.BRONZE_DIR / "reference" / "companies.csv")
    return appearing.merge(ref, on="company_name", how="left")


# ── Table de faits ─────────────────────────────────────────────────────────


def build_fact(salary: pd.DataFrame) -> pd.DataFrame:
    fact = (
        salary.groupby(FACT_GRAIN, dropna=False)
        .agg(
            avg_salary=("salary_eur", "mean"),
            min_salary=("salary_eur", "min"),
            max_salary=("salary_eur", "max"),
            job_count=("salary_eur", "size"),
        )
        .reset_index()
    )
    for col in ("avg_salary", "min_salary", "max_salary"):
        fact[col] = fact[col].round(2)
    return fact


def build_skill_popularity() -> pd.DataFrame:
    gh = _silver("github_popularity").groupby("skill").agg(
        total_stars=("stars", "sum"), total_forks=("forks", "sum")
    )
    tr = _silver("google_trends").groupby("skill").agg(avg_interest=("interest", "mean"))
    pop = gh.join(tr, how="outer").reset_index()
    pop["avg_interest"] = pop["avg_interest"].round(1)
    return pop


def build_gold() -> dict:
    """Construit dimensions + faits + popularité, écrit la couche gold, MAJ manifest."""
    salary = _salary_frame()

    dims = {
        "dim_date": build_dim_date(salary["date_posted"]),
        "dim_country": build_dim_country(),
        "dim_skill": build_dim_skill(),
        "dim_source": build_dim_source(),
        "dim_company": build_dim_company(salary),
    }
    fact = build_fact(salary)
    quality.validate(fact, quality.GOLD_FACT, "gold:fact_job")  # échec = pipeline KO
    pop = build_skill_popularity()

    for name, df in {**dims, "fact_job": fact, "skill_popularity": pop}.items():
        lake.write_parquet("gold", name, df)
        print(f"  gold  ← {name:<18} {len(df):>5} lignes")
    return {**dims, "fact_job": fact, "skill_popularity": pop}


if __name__ == "__main__":
    build_gold()
    lake.print_manifest()
