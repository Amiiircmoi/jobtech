"""Registre des sources salariales — point d'extension unique du pipeline.

Pour AJOUTER UNE SOURCE salariale, une seule chose à faire ici :
  1. écrire `generate_<src>(ctx) -> bytes`  (rendu bronze, format natif) ;
  2. écrire `clean_<src>() -> DataFrame`     (silver, au schéma SALARY_COLS) ;
  3. l'enregistrer dans REGISTRY via `SalarySource(...)`.
Le reste du pipeline (silver, gold étoile, chargement DW, Dagster) la prend en
compte automatiquement — aucune autre modification nécessaire.

Schéma silver unifié (SALARY_COLS) :
    source · date_posted · country_iso2 · skill · company · salary_eur · min/max_salary_eur
"""

import csv
import io
import json
import random
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
from faker import Faker

from . import config, transforms

SALARY_COLS = [
    "source", "date_posted", "country_iso2", "skill", "company",
    "salary_eur", "min_salary_eur", "max_salary_eur",
]

EXPERIENCE_LEVELS = [("junior", 0.80), ("confirmé", 1.00), ("senior", 1.30)]

# Sources de popularité (schéma distinct, n'alimentent pas la table de faits salaire)
POPULARITY_SOURCES = ["github_trending", "google_trends"]

RATES = transforms.load_exchange_rates(config.EXCHANGE_RATES_PATH)


# ── Contexte de génération synthétique (déterministe) ─────────────────────
@dataclass
class GenContext:
    rng: random.Random
    fake: Faker
    companies: list
    dates: list
    rates: dict

    def true_salary_eur(self, country: dict, skill: dict, exp_mult: float) -> float:
        base = config.BASE_SALARY_EUR * country["salary_index"] * skill["premium"] * exp_mult
        return round(base * self.rng.uniform(0.85, 1.20), 2)


@dataclass(frozen=True)
class SalarySource:
    name: str
    bronze_path: str
    bronze_fmt: str               # 'json' | 'csv'
    generate: Callable            # (GenContext) -> bytes
    clean: Callable               # () -> pd.DataFrame (SALARY_COLS)


def _to_csv(rows: list, fieldnames: list) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _bronze(rel: str):
    return config.BRONZE_DIR / rel


# ══════════════════════════════════════════════════════════════════════════
# Source : Adzuna (API → JSON imbriqué, salaire EUR numérique)
# ══════════════════════════════════════════════════════════════════════════
def generate_adzuna(ctx: GenContext) -> bytes:
    records = []
    for _ in range(700):
        country = ctx.rng.choice(config.COUNTRIES)
        skill = ctx.rng.choice(config.SKILLS)
        company = ctx.rng.choice(ctx.companies)
        exp_label, exp_mult = ctx.rng.choice(EXPERIENCE_LEVELS)
        true_eur = ctx.true_salary_eur(country, skill, exp_mult)
        d = ctx.rng.choice(ctx.dates)
        records.append({
            "title": f"{skill['label'].capitalize()} Developer ({exp_label})",
            "company": {"display_name": company["company_name"]},
            "location": {"display_name": f"{ctx.fake.city()}, {country['name']}"},
            "salary_min": round(true_eur * 0.9, 2),
            "salary_max": round(true_eur * 1.1, 2),
            "category": {"tag": skill["label"]},
            "country": country["iso2"].lower(),
            "created": f"{d.isoformat()}T09:00:00Z",
        })
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


def clean_adzuna() -> pd.DataFrame:
    df = pd.read_json(_bronze("adzuna/adzuna_jobs.json"))
    out = pd.DataFrame()
    out["company"] = df["company"].apply(lambda x: x.get("display_name") if isinstance(x, dict) else None)
    out["skill"] = df["category"].apply(
        lambda x: transforms.normalize_skill_label(x.get("tag")) if isinstance(x, dict) else None
    )
    out["country_iso2"] = df["country"].apply(transforms.map_country_iso2)
    out["min_salary_eur"] = df["salary_min"].astype(float)
    out["max_salary_eur"] = df["salary_max"].astype(float)
    out["salary_eur"] = out[["min_salary_eur", "max_salary_eur"]].mean(axis=1).round(2)
    out["date_posted"] = pd.to_datetime(df["created"], errors="coerce").dt.date.astype("string")
    out["source"] = "adzuna"
    return out[SALARY_COLS]


# ══════════════════════════════════════════════════════════════════════════
# Source : Indeed (scraping → CSV FR, salaire CHAÎNE avec devise locale)
# ══════════════════════════════════════════════════════════════════════════
def generate_indeed(ctx: GenContext) -> bytes:
    symbol = {"EUR": "€", "GBP": "£", "USD": "$", "CAD": "$", "AUD": "$"}
    rows = []
    for _ in range(500):
        country = ctx.rng.choice(config.COUNTRIES)
        skill = ctx.rng.choice(config.SKILLS)
        company = ctx.rng.choice(ctx.companies)
        _, exp_mult = ctx.rng.choice(EXPERIENCE_LEVELS)
        true_eur = ctx.true_salary_eur(country, skill, exp_mult)
        local = true_eur / ctx.rates.get(country["currency"], 1.0)
        sym = symbol.get(country["currency"], "€")
        rows.append({
            "Intitulé": f"{skill['label'].capitalize()} Engineer",
            "Entreprise": company["company_name"],
            "Lieu": f"{ctx.fake.city()}, {country['name']}",
            "Salaire annoncé": f"{sym}{round(local / 1000)}k",
            "Requête": skill["label"],
            "Zone": country["name"],
            "Date": ctx.rng.choice(ctx.dates).isoformat(),
        })
    return _to_csv(rows, ["Intitulé", "Entreprise", "Lieu", "Salaire annoncé", "Requête", "Zone", "Date"])


def clean_indeed() -> pd.DataFrame:
    df = pd.read_csv(_bronze("indeed/indeed_jobs.csv"))
    out = pd.DataFrame()
    out["company"] = df["Entreprise"]
    out["skill"] = df["Requête"].apply(transforms.normalize_skill_label)
    out["country_iso2"] = df["Zone"].apply(transforms.map_country_iso2)
    out["salary_eur"] = df["Salaire annoncé"].apply(lambda s: transforms.normalize_currency(s, RATES))
    out["min_salary_eur"] = float("nan")  # Indeed ne fournit pas de fourchette
    out["max_salary_eur"] = float("nan")
    out["date_posted"] = df["Date"].astype("string")
    out["source"] = "indeed"
    return out[SALARY_COLS]


# ══════════════════════════════════════════════════════════════════════════
# Source : Glassdoor (scraping → CSV, FOURCHETTE en chaîne '40k–60k€')
# ══════════════════════════════════════════════════════════════════════════
def generate_glassdoor(ctx: GenContext) -> bytes:
    rows = []
    for _ in range(350):
        country = ctx.rng.choice(config.COUNTRIES)
        skill = ctx.rng.choice(config.SKILLS)
        exp_label, exp_mult = ctx.rng.choice(EXPERIENCE_LEVELS)
        true_eur = ctx.true_salary_eur(country, skill, exp_mult)
        lo, hi = round(true_eur * 0.9 / 1000), round(true_eur * 1.1 / 1000)
        rows.append({
            "Rôle": f"{skill['label'].capitalize()} Developer",
            "Ville": ctx.fake.city(),
            "Pays": country["name"],
            "Niveau": exp_label,
            "skill": skill["label"],
            "salary_range": f"{lo}k–{hi}k€",
            "date_posted": ctx.rng.choice(ctx.dates).isoformat(),
        })
    return _to_csv(rows, ["Rôle", "Ville", "Pays", "Niveau", "skill", "salary_range", "date_posted"])


def clean_glassdoor() -> pd.DataFrame:
    df = pd.read_csv(_bronze("glassdoor/glassdoor_salaries.csv"))
    ranges = df["salary_range"].apply(transforms.parse_salary_range)
    mins = ranges.apply(lambda t: t[0])
    maxs = ranges.apply(lambda t: t[1])
    out = pd.DataFrame()
    out["company"] = pd.NA
    out["skill"] = df["skill"].apply(transforms.normalize_skill_label)
    out["country_iso2"] = df["Pays"].apply(transforms.map_country_iso2)
    out["min_salary_eur"] = mins
    out["max_salary_eur"] = maxs
    out["salary_eur"] = ((mins + maxs) / 2).round(2)
    out["date_posted"] = df["date_posted"].astype("string")
    out["source"] = "glassdoor"
    return out[SALARY_COLS]


# ══════════════════════════════════════════════════════════════════════════
# Source : Stack Overflow Survey (CSV, USD numérique, multi-compétences ';')
# ══════════════════════════════════════════════════════════════════════════
def generate_so_survey(ctx: GenContext) -> bytes:
    rows = []
    labels = [s["label"] for s in config.SKILLS]
    for _ in range(1500):
        country = ctx.rng.choice(config.COUNTRIES)
        skills = ctx.rng.sample(labels, ctx.rng.randint(1, 3))
        objs = [s for s in config.SKILLS if s["label"] in skills]
        avg_premium = sum(s["premium"] for s in objs) / len(objs)
        _, exp_mult = ctx.rng.choice(EXPERIENCE_LEVELS)
        true_eur = config.BASE_SALARY_EUR * country["salary_index"] * avg_premium * exp_mult
        true_eur = round(true_eur * ctx.rng.uniform(0.85, 1.20), 2)
        rows.append({
            "Country": country["name"],
            "ConvertedCompYearly": int(round(true_eur / ctx.rates["USD"])),
            "LanguageHaveWorkedWith": ";".join(skills),
        })
    return _to_csv(rows, ["Country", "ConvertedCompYearly", "LanguageHaveWorkedWith"])


def clean_so_survey() -> pd.DataFrame:
    df = pd.read_csv(_bronze("so_survey/so_survey.csv"))
    df["country_iso2"] = df["Country"].apply(transforms.map_country_iso2)
    df["salary_eur"] = df["ConvertedCompYearly"].apply(
        lambda v: transforms.normalize_currency(f"USD{v}", RATES)
    )
    df["skill_list"] = df["LanguageHaveWorkedWith"].fillna("").apply(
        lambda s: [transforms.normalize_skill_label(x) for x in str(s).split(";") if x]
    )
    df = df.explode("skill_list").rename(columns={"skill_list": "skill"}).dropna(subset=["skill"])
    out = pd.DataFrame()
    out["company"] = pd.NA
    out["skill"] = df["skill"].values
    out["country_iso2"] = df["country_iso2"].values
    out["salary_eur"] = df["salary_eur"].values
    out["min_salary_eur"] = float("nan")  # enquête : pas de fourchette min/max
    out["max_salary_eur"] = float("nan")
    out["date_posted"] = config.AS_OF_DATE
    out["source"] = "so_survey"
    return out[SALARY_COLS]


# ── REGISTRE (l'unique endroit à éditer pour ajouter une source salariale) ──
# Pour un exemple complet d'ajout de source (Welcome to the Jungle), voir
# docs/adr/ajout-source.md.
REGISTRY: list[SalarySource] = [
    SalarySource("adzuna", "adzuna/adzuna_jobs.json", "json", generate_adzuna, clean_adzuna),
    SalarySource("indeed", "indeed/indeed_jobs.csv", "csv", generate_indeed, clean_indeed),
    SalarySource("glassdoor", "glassdoor/glassdoor_salaries.csv", "csv", generate_glassdoor, clean_glassdoor),
    SalarySource("so_survey", "so_survey/so_survey.csv", "csv", generate_so_survey, clean_so_survey),
]


def salary_source_names() -> list:
    return [s.name for s in REGISTRY]


def all_source_names() -> list:
    return salary_source_names() + POPULARITY_SOURCES
