"""Qualité de données — schémas de validation Pandera (fail-fast).

Pourquoi Pandera (et pas Great Expectations / checks maison) : schéma-as-code
pandas, déclaratif, **léger** (pas de data-docs/store/CLI à exploiter), lève une
exception en cas d'écart → branché dans le pipeline, **un échec = pipeline KO**.
Right-sizing : GE serait surdimensionné ici ; le maison réinventerait Pandera.

Contrôles : présence/typage des colonnes, plages plausibles (cohérence devise :
un salaire normalisé en EUR doit tomber dans une fourchette réaliste), non-nul,
cohérence min ≤ avg ≤ max.
"""

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

# Fourchette de plausibilité d'un salaire annuel normalisé en EUR.
# Sert de garde-fou « cohérence devise » : une conversion ratée sortirait de la bande.
_EUR_MIN, _EUR_MAX = 1_000.0, 500_000.0


class DataQualityError(RuntimeError):
    """Levée quand un jeu de données viole son contrat de qualité."""


# ── Schéma SILVER (sources salariales unifiées) ───────────────────────────
SILVER_SALARY = DataFrameSchema(
    {
        "source": Column(str, Check.str_length(min_value=2)),
        "date_posted": Column(str, Check.str_matches(r"^\d{4}-\d{2}-\d{2}$")),
        "country_iso2": Column(str, Check.str_length(2, 2)),
        "skill": Column(str, Check.str_length(min_value=1)),
        "company": Column(object, nullable=True),
        "salary_eur": Column(float, Check.in_range(_EUR_MIN, _EUR_MAX)),
        "min_salary_eur": Column(float, nullable=True),
        "max_salary_eur": Column(float, nullable=True),
    },
    strict=True,
    coerce=True,
)

# ── Schéma GOLD (table de faits) ──────────────────────────────────────────
GOLD_FACT = DataFrameSchema(
    {
        "date_posted": Column(str, Check.str_matches(r"^\d{4}-\d{2}-\d{2}$")),
        "country_iso2": Column(str, Check.str_length(2, 2)),
        "skill": Column(str, Check.str_length(min_value=1)),
        "company": Column(str, Check.str_length(min_value=1)),
        "source": Column(str, Check.str_length(min_value=2)),
        "avg_salary": Column(float, Check.in_range(_EUR_MIN, _EUR_MAX)),
        "min_salary": Column(float, Check.in_range(_EUR_MIN, _EUR_MAX)),
        "max_salary": Column(float, Check.in_range(_EUR_MIN, _EUR_MAX)),
        "job_count": Column(int, Check.ge(1)),
    },
    checks=[
        Check(lambda df: df["min_salary"] <= df["avg_salary"], error="min > avg"),
        Check(lambda df: df["avg_salary"] <= df["max_salary"], error="avg > max"),
    ],
    strict=True,
    coerce=True,
)


def validate(df, schema: DataFrameSchema, name: str):
    """Valide `df` contre `schema` ; lève DataQualityError (toutes erreurs groupées)."""
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases[["column", "check", "failure_case"]].head(10).to_dict("records")
        raise DataQualityError(f"Qualité de données KO sur '{name}': {cases}") from exc
