"""Génération synthétique reproductible → couche BRONZE.

Pourquoi : les scrapers réels (Indeed, Glassdoor) sont fragiles (anti-bot) et non
rejouables en démo. Ce module produit, de façon **déterministe** (seed figée), des
dumps bruts au **format natif de chaque source**. Les sources salariales sont
décrites dans `pipeline/sources.py` (registre extensible) ; ici on n'ajoute que
le contexte de génération, les sources de popularité et le registre des entreprises.

Aucune donnée personnelle : entreprises et montants sont fictifs (RGPD).
"""

import json
import random
from datetime import date, datetime, timedelta

from faker import Faker

from . import config, lake, sources


def _rng() -> random.Random:
    return random.Random(config.RANDOM_SEED)


def _faker() -> Faker:
    fake = Faker("en_US")
    Faker.seed(config.RANDOM_SEED)
    return fake


def _date_pool(rng: random.Random) -> list[date]:
    end = datetime.strptime(config.AS_OF_DATE, "%Y-%m-%d").date()
    start = end - timedelta(days=config.HISTORY_DAYS)
    span = (end - start).days
    return [start + timedelta(days=rng.randint(0, span)) for _ in range(span + 1)]


def _companies(fake: Faker, n: int = 40) -> list[dict]:
    seen, out = set(), []
    while len(out) < n:
        name = fake.company()
        if name in seen:
            continue
        seen.add(name)
        out.append({
            "company_name": name,
            "workforce_size": fake.random_element(config.WORKFORCE_SIZES),
            "sector": fake.random_element(config.SECTORS),
        })
    return out


def _context() -> sources.GenContext:
    rng, fake = _rng(), _faker()
    rates = json.loads(config.EXCHANGE_RATES_PATH.read_text())
    return sources.GenContext(rng=rng, fake=fake, companies=_companies(fake), dates=_date_pool(rng), rates=rates)


# ── Sources de popularité (schéma distinct, hors registre salarial) ───────
def gen_github_trending(ctx: sources.GenContext) -> bytes:
    languages = [s for s in config.SKILLS if s["group"] == "language"]
    records = []
    for skill in languages:
        for _ in range(10):
            records.append({
                "repo": f"{ctx.fake.user_name()}/{ctx.fake.slug()}",
                "description": ctx.fake.sentence(nb_words=8),
                "stars": f"{ctx.rng.randint(50, 50000):,}",
                "forks": ctx.rng.randint(5, 8000),
                "language": skill["label"].capitalize(),
                "period": "daily",
            })
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


def gen_google_trends(ctx: sources.GenContext) -> bytes:
    rows = []
    skills = [s["label"] for s in config.SKILLS[:6]]
    countries = ["FR", "GB", "US", "DE"]
    end = datetime.strptime(config.AS_OF_DATE, "%Y-%m-%d").date()
    weeks = [end - timedelta(weeks=w) for w in range(13)]
    for iso2 in countries:
        for kw in skills:
            base = ctx.rng.randint(40, 80)
            for w in weeks:
                interest = max(0, min(100, base + ctx.rng.randint(-15, 15)))
                rows.append({"date": w.isoformat(), "keyword": kw, "country": iso2, "interest": interest})
    return sources._to_csv(rows, ["date", "keyword", "country", "interest"])


def generate_all() -> dict:
    """Génère les sources salariales (registre) + popularité + registre des entreprises."""
    ctx = _context()
    out = {}
    for src in sources.REGISTRY:
        content = src.generate(ctx)
        out[src.name] = lake.write_bytes("bronze", src.bronze_path, content, source=src.name, fmt=src.bronze_fmt)
        print(f"  bronze ← {src.name:<16} {src.bronze_path}")

    for name, rel, fn in [
        ("github_trending", "github_trending/github_trending.json", gen_github_trending),
        ("google_trends", "google_trends/google_trends.csv", gen_google_trends),
    ]:
        fmt = "json" if rel.endswith(".json") else "csv"
        out[name] = lake.write_bytes("bronze", rel, fn(ctx), source=name, fmt=fmt)
        print(f"  bronze ← {name:<16} {rel}")

    ref = sources._to_csv(ctx.companies, ["company_name", "workforce_size", "sector"])
    out["companies_ref"] = lake.write_bytes("bronze", "reference/companies.csv", ref, source="companies_ref", fmt="csv")
    print(f"  bronze ← {'companies_ref':<16} reference/companies.csv")
    return out


if __name__ == "__main__":
    generate_all()
    lake.print_manifest()
