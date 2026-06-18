"""Configuration centrale du pipeline : chemins du datalake, registres, DB."""

from pathlib import Path

import environ

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent

env = environ.Env()
environ.Env.read_env(REPO_ROOT / ".env")

# ── Datalake médaillon (régénérable, hors Git) ────────────────────────────
DATA_DIR = REPO_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"   # dumps bruts immuables, format natif des sources
SILVER_DIR = DATA_DIR / "silver"   # nettoyé, typé, normalisé (Parquet)
GOLD_DIR = DATA_DIR / "gold"       # agrégats métier, prêt pour le schéma étoile
MANIFEST_PATH = DATA_DIR / "manifest.json"

EXCHANGE_RATES_PATH = REPO_ROOT / "config" / "exchange_rates.json"
DDL_PATH = REPO_ROOT / "sql" / "create_dw.sql"

DATABASE_URL = env(
    "DATABASE_URL",
    default="postgresql://jobtech:jobtech_dev_pwd@localhost:5432/jobtech",
)

# ── Reproductibilité ──────────────────────────────────────────────────────
# Date de référence figée → la génération synthétique est déterministe.
AS_OF_DATE = "2026-06-15"
RANDOM_SEED = 42
HISTORY_DAYS = 90  # profondeur d'historique des offres synthétiques

# ── Référentiels (dimensions) ─────────────────────────────────────────────
# La liste des sources est dérivée du registre `pipeline/sources.py` (extensibilité).

# iso2, nom, région, monnaie iso3 (présente dans exchange_rates.json), indice salaire (FR=1.0)
COUNTRIES = [
    {"iso2": "FR", "name": "France", "region": "Europe", "currency": "EUR", "salary_index": 1.00},
    {"iso2": "DE", "name": "Germany", "region": "Europe", "currency": "EUR", "salary_index": 1.10},
    {"iso2": "GB", "name": "United Kingdom", "region": "Europe", "currency": "GBP", "salary_index": 1.15},
    {"iso2": "ES", "name": "Spain", "region": "Europe", "currency": "EUR", "salary_index": 0.80},
    {"iso2": "IT", "name": "Italy", "region": "Europe", "currency": "EUR", "salary_index": 0.82},
    {"iso2": "NL", "name": "Netherlands", "region": "Europe", "currency": "EUR", "salary_index": 1.12},
    {"iso2": "US", "name": "United States", "region": "North America", "currency": "USD", "salary_index": 1.45},
    {"iso2": "CA", "name": "Canada", "region": "North America", "currency": "CAD", "salary_index": 1.20},
    {"iso2": "AU", "name": "Australia", "region": "Oceania", "currency": "AUD", "salary_index": 1.18},
]

# label normalisé, groupe, prime salariale relative
SKILLS = [
    {"label": "python", "group": "language", "premium": 1.05},
    {"label": "javascript", "group": "language", "premium": 0.95},
    {"label": "typescript", "group": "language", "premium": 1.02},
    {"label": "java", "group": "language", "premium": 1.00},
    {"label": "go", "group": "language", "premium": 1.12},
    {"label": "rust", "group": "language", "premium": 1.18},
    {"label": "sql", "group": "database", "premium": 0.90},
    {"label": "react", "group": "framework", "premium": 1.00},
    {"label": "django", "group": "framework", "premium": 1.00},
    {"label": "docker", "group": "devops", "premium": 1.05},
    {"label": "kubernetes", "group": "devops", "premium": 1.20},
    {"label": "aws", "group": "cloud", "premium": 1.15},
]

SECTORS = ["Software", "Finance", "E-commerce", "Healthtech", "Gaming", "Consulting", "Telecom"]
WORKFORCE_SIZES = ["1-50", "51-200", "201-1000", "1001-5000", "5000+"]

BASE_SALARY_EUR = 55000  # salaire de référence (FR, prime 1.0) avant bruit
