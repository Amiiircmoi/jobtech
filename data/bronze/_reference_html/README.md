# Bronze — pièce « non structurée » réelle

Ce dossier conserve un **dump HTML brut réel** dans la couche bronze, pour montrer que
le datalake **intègre et stocke des données non structurées** (« fichiers de tout
type »), aux côtés du semi-structuré (JSON) et du structuré (CSV/Parquet).

## `hn_jobs_sample.html`

| Attribut | Valeur |
|---|---|
| **Source** | Hacker News — page publique d'offres d'emploi (`https://news.ycombinator.com/jobs`) |
| **Nature** | HTML brut **non structuré** (DOM complet, non parsé) |
| **Ingéré le** | 2026-06-17 (HTTP 200, ~23 Ko) |
| **Données personnelles** | **Aucune** — annonces publiques (entreprise + intitulé), pas de PII → cohérent avec la politique RGPD « zéro donnée personnelle » (cf. [`docs/data-governance.md`](../../../docs/data-governance.md)) |
| **Base légale / robots** | page publique, `robots.txt` autorise `/jobs` ; User-Agent identifiant + usage analytique |

## Statut & limite honnête

- **Ingéré + stocké** dans bronze (couche immuable) = **fait**.
- **Parsing → silver = étape future** : aujourd'hui le pipeline silver salarial s'appuie
  sur les 6 sources déclarées ; ce dump illustre la **capacité du lac à héberger du non
  structuré**. Le parcours de parsing HTML est par ailleurs démontré au code par
  `pipeline/ingest_real.py::fetch_github_trending` (BeautifulSoup) — conservé comme
  référence du chemin DOM → JSON.

> Tout le reste de `data/` reste **gitignoré** (régénérable par le pipeline) ; seul ce
> dossier `_reference_html/` est versionné, via une allowlist `.gitignore` ciblée.
