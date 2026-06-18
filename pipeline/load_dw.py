"""Chargement vers le Data Warehouse PostgreSQL (schéma étoile).

Deux modes, mêmes briques d'UPSERT :
  • `load()` (full-refresh) : TRUNCATE + rechargement complet depuis gold, dans UNE
    transaction → le DWH reflète exactement la couche gold (batch périodique).
  • `load_increment(dims, fact)` : UPSERT sans TRUNCATE → micro-batch incrémental ;
    n'ajoute/maj que le lot fourni, sans toucher l'historique.
Idempotent (INSERT ... ON CONFLICT), respecte les FK (dims avant faits), avec
contraintes d'intégrité et transactions pour un chargement reproductible.
"""

import re

import pandas as pd
import psycopg

from . import config

# nom logique → (table, colonnes, SQL d'upsert)
_DIM_SPECS = {
    "dim_date": (
        "d_date",
        ["date_key", "day", "month", "quarter", "year", "day_week"],
        """INSERT INTO d_date (date_key, day, month, quarter, year, day_week)
           VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (date_key) DO NOTHING""",
    ),
    "dim_country": (
        "d_country",
        ["iso2", "country_name", "region", "monnaie_iso3"],
        """INSERT INTO d_country (iso2, country_name, region, monnaie_iso3)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (iso2) DO UPDATE SET country_name = EXCLUDED.country_name,
             region = EXCLUDED.region, monnaie_iso3 = EXCLUDED.monnaie_iso3""",
    ),
    "dim_company": (
        "d_company",
        ["company_name", "workforce_size", "sector"],
        """INSERT INTO d_company (company_name, workforce_size, sector)
           VALUES (%s, %s, %s)
           ON CONFLICT (company_name) DO UPDATE SET workforce_size = EXCLUDED.workforce_size,
             sector = EXCLUDED.sector""",
    ),
    "dim_skill": (
        "d_skill",
        ["tech_label", "skill_group"],
        """INSERT INTO d_skill (tech_label, skill_group) VALUES (%s, %s)
           ON CONFLICT (tech_label) DO UPDATE SET skill_group = EXCLUDED.skill_group""",
    ),
    "dim_source": (
        "d_source",
        ["source_name"],
        "INSERT INTO d_source (source_name) VALUES (%s) ON CONFLICT (source_name) DO NOTHING",
    ),
}

_FACT_SQL = """INSERT INTO fact_job
    (date_key, id_country, id_company, id_skill, id_source,
     avg_salary, min_salary, max_salary, job_count)
  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
  ON CONFLICT (date_key, id_country, id_company, id_skill, id_source) DO UPDATE
    SET avg_salary = EXCLUDED.avg_salary, min_salary = EXCLUDED.min_salary,
        max_salary = EXCLUDED.max_salary, job_count = EXCLUDED.job_count"""

_TABLES = ["d_date", "d_country", "d_company", "d_skill", "d_source", "fact_job"]


def _connect():
    return psycopg.connect(config.DATABASE_URL)


def ensure_schema(conn) -> None:
    """Applique le DDL du schéma étoile (idempotent : CREATE TABLE IF NOT EXISTS)."""
    sql = re.sub(r"--[^\n]*", "", config.DDL_PATH.read_text())
    for stmt in (s.strip() for s in sql.split(";")):
        if stmt:
            conn.execute(stmt)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    """NaN/NA → None pour psycopg."""
    return df.astype(object).where(pd.notna(df), None)


def _gold(name: str) -> pd.DataFrame:
    return pd.read_parquet(config.GOLD_DIR / f"{name}.parquet")


def _upsert(conn, sql: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


def _id_map(conn, table: str, key_col: str, id_col: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {key_col}, {id_col} FROM {table}")
        return dict(cur.fetchall())


def _upsert_dims(conn, dims: dict) -> None:
    for name, (_table, cols, sql) in _DIM_SPECS.items():
        if name in dims and len(dims[name]):
            df = _prep(dims[name])
            _upsert(conn, sql, list(df[cols].itertuples(index=False, name=None)))


def _upsert_facts(conn, fact: pd.DataFrame) -> None:
    fact = _prep(fact)
    cid = _id_map(conn, "d_country", "iso2", "id_country")
    coid = _id_map(conn, "d_company", "company_name", "id_company")
    sid = _id_map(conn, "d_skill", "tech_label", "id_skill")
    soid = _id_map(conn, "d_source", "source_name", "id_source")
    rows = [
        (r.date_posted, cid[r.country_iso2], coid[r.company], sid[r.skill], soid[r.source],
         r.avg_salary, r.min_salary, r.max_salary, int(r.job_count))
        for r in fact.itertuples(index=False)
    ]
    _upsert(conn, _FACT_SQL, rows)


def _counts(conn) -> dict:
    out = {}
    with conn.cursor() as cur:
        for t in _TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def load(full_refresh: bool = True) -> dict:
    """Charge la couche gold complète. full_refresh=True → TRUNCATE + reload (batch)."""
    with _connect() as conn:
        ensure_schema(conn)
        if full_refresh:
            conn.execute("TRUNCATE fact_job, d_date, d_country, d_company, d_skill, d_source RESTART IDENTITY CASCADE")
        _upsert_dims(conn, {n: _gold(n) for n in _DIM_SPECS})
        _upsert_facts(conn, _gold("fact_job"))
        return _counts(conn)


def load_increment(dims: dict, fact: pd.DataFrame) -> dict:
    """Micro-batch : UPSERT d'un lot (dims + faits) SANS TRUNCATE."""
    with _connect() as conn:
        ensure_schema(conn)
        _upsert_dims(conn, dims)
        _upsert_facts(conn, fact)
        return _counts(conn)


if __name__ == "__main__":
    counts = load()
    print("DW chargé (PostgreSQL) :")
    for t, c in counts.items():
        print(f"  {t:<12} {c:>6} lignes")
