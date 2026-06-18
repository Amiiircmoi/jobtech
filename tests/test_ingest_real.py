"""Parité réel ↔ synthétique — preuve que « brancher le réel ne change pas
une ligne de silver » et couverture du module d'ingestion réelle.

On EXERCE le vrai chemin d'ingestion (`pipeline/ingest_real.py`) avec le réseau
mocké par des **échantillons réel-shaped figés** (`tests/fixtures/`), puis on passe
la sortie bronze dans les MÊMES nettoyeurs silver (`pipeline/sources.py`) que le
synthétique. Si les colonnes/types/qualité tiennent, la promesse de parité est
**prouvée**, pas seulement affirmée.

Voir la décision d'architecture `docs/adr/sources-reelles-vs-synthetiques.md`.
"""

import io
import json
import pathlib
import zipfile

import pytest

from pipeline import config, ingest_real, lake, quality, sources

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class _FakeResp:
    """Réponse HTTP minimale (mock de requests.get)."""

    def __init__(self, *, json_data=None, content=b""):
        self._json = json_data
        self.content = content
        self.text = content.decode("utf-8", "replace") if content else ""

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


@pytest.fixture
def bronze_tmp(monkeypatch, tmp_path):
    """Redirige la couche bronze vers un dossier temporaire (n'altère pas data/)."""
    b = tmp_path / "bronze"
    b.mkdir(parents=True)
    monkeypatch.setattr(config, "BRONZE_DIR", b)          # utilisé par sources._bronze()
    monkeypatch.setitem(lake._LAYERS, "bronze", b)        # utilisé par lake.write_bytes()
    return b


def test_adzuna_real_shape_matches_silver_contract(bronze_tmp, monkeypatch):
    """Réponse API Adzuna réelle-shaped → fetch_adzuna → clean_adzuna == schéma silver."""
    payload = json.loads((FIXTURES / "adzuna_api_sample.json").read_text())
    monkeypatch.setattr(ingest_real.requests, "get", lambda *a, **k: _FakeResp(json_data=payload))
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")

    # Chemin d'ingestion RÉEL (réseau mocké) → écrit bronze au format natif
    ingest_real.fetch_adzuna(["fr"], pages=1)
    assert (bronze_tmp / "adzuna" / "adzuna_jobs.json").exists()

    # MÊME nettoyeur silver que le synthétique
    df = sources.clean_adzuna()
    assert list(df.columns) == sources.SALARY_COLS          # parité de schéma
    assert len(df) == 10
    assert df["country_iso2"].eq("FR").all()                # 'fr' → ISO2 'FR'
    assert df["salary_eur"].between(1000, 500000).all()
    # La sortie passe le contrat qualité silver (gate Pandera) sans adaptation
    quality.validate(df, quality.SILVER_SALARY, "test:adzuna-real")


def test_so_survey_real_shape_matches_silver_contract(bronze_tmp, monkeypatch):
    """ZIP SO Survey réel-shaped (colonnes surnuméraires) → download → clean == silver."""
    csv_bytes = (FIXTURES / "so_survey_sample.csv").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stack-overflow-developer-survey-2024/survey_results_public.csv", csv_bytes)
    monkeypatch.setattr(ingest_real.requests, "get", lambda *a, **k: _FakeResp(content=buf.getvalue()))

    ingest_real.download_so_survey(2024)
    assert (bronze_tmp / "so_survey" / "so_survey.csv").exists()

    df = sources.clean_so_survey()
    assert list(df.columns) == sources.SALARY_COLS
    # éclatement multi-compétences : 10 répondants → >10 lignes (répondant × skill)
    assert len(df) > 10
    assert df["country_iso2"].str.len().eq(2).all()
    assert df["salary_eur"].between(1000, 500000).all()
    quality.validate(df, quality.SILVER_SALARY, "test:so-survey-real")


def test_scrape_indeed_is_explicit_reference_stub():
    """Indeed/Glassdoor : référence non activée → NotImplementedError honnête (pas un faux ✅)."""
    with pytest.raises(NotImplementedError):
        ingest_real.scrape_indeed(["python"], ["Paris"])
