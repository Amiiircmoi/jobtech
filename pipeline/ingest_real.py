"""Ingestion des SOURCES RÉELLES vers la couche bronze (référence, hors démo).

⚠️ Ce module est le chemin d'ingestion « production » : il appelle de vraies API
   (Adzuna, Stack Overflow) et scrape des sites (Indeed, Glassdoor via Selenium —
   dépendances dans requirements-scraping.txt). Il N'EST PAS exécuté en démo ni en
   CI car les sources sont fragiles (anti-bot, quotas). Le chemin reproductible est
   `pipeline.synthetic`. Voir `pipeline/run.py`.

Secrets : aucun en dur — clés Adzuna lues via les variables d'environnement
(ADZUNA_APP_ID / ADZUNA_APP_KEY), conformément à la politique de sécurité (.env).

Conformité RGPD : on ne conserve que des données d'offres/salaires agrégées et
des dépôts publics — aucune donnée personnelle identifiante.
"""

import json
import os

import requests
from bs4 import BeautifulSoup

from . import lake


# ── 1. Adzuna (API REST officielle) ───────────────────────────────────────
def fetch_adzuna(countries, pages=5, results_per_page=50) -> None:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY absents de l'environnement (.env)")
    all_jobs = []
    for country in countries:
        for page in range(1, pages + 1):
            url = (
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
                f"?app_id={app_id}&app_key={app_key}&results_per_page={results_per_page}"
            )
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            jobs = resp.json().get("results", [])
            if not jobs:
                break
            for j in jobs:  # aligne sur le contrat bronze (country + category.tag)
                j.setdefault("country", country)
                cat = j.get("category") or {}
                cat.setdefault("tag", (cat.get("label") or "").lower())
                j["category"] = cat
            all_jobs.extend(jobs)
    lake.write_bytes(
        "bronze", "adzuna/adzuna_jobs.json",
        json.dumps(all_jobs, ensure_ascii=False, indent=2).encode("utf-8"),
        source="adzuna", fmt="json",
    )
    print(f"Adzuna: {len(all_jobs)} offres → bronze")


# ── 2. GitHub Trending (scraping HTML public) ──────────────────────────────
def fetch_github_trending(languages, since="daily") -> None:
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    records = []
    for lang in languages:
        url = f"https://github.com/trending/{lang}?since={since}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"GitHub {lang}: {e}")
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        for repo in soup.find_all("article", class_="Box-row"):
            header = repo.find("h2") or repo.find("h1")
            link = header.find("a") if header else None
            star_el = repo.find("a", href=lambda x: x and x.endswith("/stargazers"))
            records.append(
                {
                    "repo": link.get_text(strip=True).replace(" ", "") if link else None,
                    "description": (repo.find("p").get_text(strip=True) if repo.find("p") else None),
                    "stars": star_el.get_text(strip=True) if star_el else "0",
                    "forks": 0,
                    "language": lang.capitalize(),
                    "period": since,
                }
            )
    lake.write_bytes(
        "bronze", "github_trending/github_trending.json",
        json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8"),
        source="github_trending", fmt="json",
    )
    print(f"GitHub Trending: {len(records)} dépôts → bronze")


# ── 3. Stack Overflow Developer Survey (téléchargement CSV/ZIP) ────────────
def download_so_survey(year=2024) -> None:
    import io
    import zipfile

    url = f"https://survey.stackoverflow.co/datasets/stack-overflow-developer-survey-{year}.zip"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith("survey_results_public.csv"))
        content = z.read(name)
    lake.write_bytes("bronze", "so_survey/so_survey.csv", content, source="so_survey", fmt="csv")
    print(f"SO Survey {year}: {len(content)} octets → bronze")


# ── 4. Google Trends (pytrends) ────────────────────────────────────────────
def fetch_google_trends(keywords, countries) -> None:
    """Popularité hebdomadaire via pytrends. Sortie alignée sur le schéma silver
    (date, keyword, country, interest) — identique au générateur synthétique."""
    from pytrends.request import TrendReq

    pytrends = TrendReq()
    rows = []
    for country in countries:
        for kw in keywords:
            pytrends.build_payload([kw], geo=country)
            df = pytrends.interest_over_time()
            if df.empty:
                continue
            for idx, val in df[kw].items():
                rows.append({
                    "date": idx.date().isoformat(),
                    "keyword": kw,
                    "country": country,
                    "interest": int(val),
                })
    from . import sources  # réutilise l'helper CSV
    lake.write_bytes(
        "bronze", "google_trends/google_trends.csv",
        sources._to_csv(rows, ["date", "keyword", "country", "interest"]),
        source="google_trends", fmt="csv",
    )
    print(f"Google Trends: {len(rows)} points → bronze")


# ── 5. Indeed / Glassdoor (Selenium — imports paresseux) ───────────────────
def scrape_indeed(queries, locations, pages=3, pause=5) -> None:
    """Scraper navigateur (Indeed/Glassdoor) — nécessite requirements-scraping.txt.

    Conservé comme référence du parcours DOM + gestion captcha. Non activé par
    défaut (fragile, anti-bot) ; le chemin reproductible est `pipeline.synthetic`.
    """
    raise NotImplementedError(
        "Active selenium + undetected-chromedriver (requirements-scraping.txt) pour scraper Indeed."
    )


if __name__ == "__main__":
    # Exécution réelle (nécessite les clés et le réseau) — non utilisé en démo.
    fetch_adzuna(["gb", "us", "fr"])
    fetch_github_trending(["python", "javascript", "java"])
    download_so_survey(2024)
