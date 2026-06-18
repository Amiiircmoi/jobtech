"""Tests du garde-fou qualité (Pandera) : il doit PASSER sur des données valides
et ÉCHOUER (DataQualityError) sur des données hors contrat."""

import numpy as np
import pandas as pd
import pytest

from pipeline import quality


def _valid_silver_row() -> pd.DataFrame:
    return pd.DataFrame({
        "source": ["adzuna"],
        "date_posted": ["2026-06-01"],
        "country_iso2": ["FR"],
        "skill": ["python"],
        "company": ["ACME"],
        "salary_eur": [55000.0],
        "min_salary_eur": [np.nan],
        "max_salary_eur": [np.nan],
    })


def test_silver_valid_passes():
    out = quality.validate(_valid_silver_row(), quality.SILVER_SALARY, "test")
    assert len(out) == 1


def test_silver_rejects_implausible_salary():
    bad = _valid_silver_row()
    bad["salary_eur"] = [12.0]  # hors fourchette EUR plausible → conversion suspecte
    with pytest.raises(quality.DataQualityError):
        quality.validate(bad, quality.SILVER_SALARY, "test")


def test_silver_rejects_bad_country_code():
    bad = _valid_silver_row()
    bad["country_iso2"] = ["FRANCE"]  # doit être ISO2 (2 caractères)
    with pytest.raises(quality.DataQualityError):
        quality.validate(bad, quality.SILVER_SALARY, "test")


def test_gold_fact_rejects_min_gt_max():
    fact = pd.DataFrame({
        "date_posted": ["2026-06-01"], "country_iso2": ["FR"], "skill": ["python"],
        "company": ["ACME"], "source": ["adzuna"],
        "avg_salary": [55000.0], "min_salary": [60000.0], "max_salary": [50000.0],
        "job_count": [3],
    })
    with pytest.raises(quality.DataQualityError):
        quality.validate(fact, quality.GOLD_FACT, "test")
