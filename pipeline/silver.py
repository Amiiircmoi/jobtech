"""Couche SILVER : bronze (formats natifs hétérogènes) → données nettoyées, typées,
normalisées (Parquet). Les nettoyeurs des sources salariales vivent dans le registre
`pipeline/sources.py` ; ce module orchestre le nettoyage + contrôle qualité, et gère
les sources de popularité (GitHub, Google Trends) au schéma distinct.
"""

import pandas as pd

from . import config, lake, quality, sources, transforms


def _bronze(rel: str):
    return config.BRONZE_DIR / rel


def clean_github() -> pd.DataFrame:
    df = pd.read_json(_bronze("github_trending/github_trending.json"))
    out = pd.DataFrame()
    out["skill"] = df["language"].apply(transforms.normalize_skill_label)
    out["stars"] = df["stars"].astype(str).str.replace(",", "", regex=False).astype(int)
    out["forks"] = df["forks"].fillna(0).astype(int)
    out["source"] = "github_trending"
    return out


def clean_trends() -> pd.DataFrame:
    df = pd.read_csv(_bronze("google_trends/google_trends.csv"))
    out = pd.DataFrame()
    out["date"] = df["date"].astype("string")
    out["skill"] = df["keyword"].apply(transforms.normalize_skill_label)
    out["country_iso2"] = df["country"]
    out["interest"] = df["interest"].astype(int)
    out["source"] = "google_trends"
    return out


def _quality_filter(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Rejette les lignes inexploitables (pays/skill/salaire manquants). Journalise le taux."""
    before = len(df)
    df = df.dropna(subset=["country_iso2", "skill", "salary_eur"])
    df = df[df["salary_eur"] > 0]
    rejected = before - len(df)
    print(f"  silver ← {source:<16} {len(df):>5}/{before:<5} lignes valides ({rejected} rejetées)")
    return df


def build_silver() -> dict:
    """Nettoie les sources du registre + popularité, écrit la couche silver, MAJ manifest."""
    out = {}
    for src in sources.REGISTRY:
        df = _quality_filter(src.clean(), src.name)
        quality.validate(df, quality.SILVER_SALARY, f"silver:{src.name}")  # échec = pipeline KO
        lake.write_parquet("silver", src.name, df, source=src.name)
        out[src.name] = df

    gh = clean_github()
    lake.write_parquet("silver", "github_popularity", gh, source="github_trending")
    print(f"  silver ← {'github_trending':<16} {len(gh):>5} lignes (popularité)")
    tr = clean_trends()
    lake.write_parquet("silver", "google_trends", tr, source="google_trends")
    print(f"  silver ← {'google_trends':<16} {len(tr):>5} lignes (popularité)")
    out["github_popularity"], out["google_trends"] = gh, tr
    return out


if __name__ == "__main__":
    build_silver()
    lake.print_manifest()
