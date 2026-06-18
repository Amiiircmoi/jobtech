# Démonstration — Ajouter une source de données

> Objectif : prouver que le pipeline est **extensible** — ajouter une nouvelle
> source ne touche qu'**un seul fichier** (`pipeline/sources.py`) ; silver, le
> schéma étoile, le chargement DWH et l'API la prennent en compte automatiquement.

## Le contrat

Le pipeline est piloté par un **registre** (`pipeline/sources.py` → `REGISTRY`).
Une source salariale est un `SalarySource(name, bronze_path, bronze_fmt, generate, clean)` :
- `generate(ctx) -> bytes` : produit le dump bronze au **format natif** de la source ;
- `clean() -> DataFrame` : nettoie vers le **schéma silver unifié** (`SALARY_COLS`).

## Exemple complet : Welcome to the Jungle (`wttj`)

Job board EU exposant des fourchettes EUR structurées. **Diff intégral** à appliquer
dans `pipeline/sources.py` :

```python
def generate_wttj(ctx: GenContext) -> bytes:
    records = []
    for _ in range(400):
        country = ctx.rng.choice(config.COUNTRIES)
        skill = ctx.rng.choice(config.SKILLS)
        company = ctx.rng.choice(ctx.companies)
        _, exp_mult = ctx.rng.choice(EXPERIENCE_LEVELS)
        true_eur = ctx.true_salary_eur(country, skill, exp_mult)
        records.append({
            "name": f"{skill['label'].capitalize()} Engineer",
            "organization": {"name": company["company_name"]},
            "office": {"country": country["name"]},
            "profession": skill["label"],
            "compensation": {"min": round(true_eur*0.92, 2), "max": round(true_eur*1.08, 2),
                             "currency": "EUR", "period": "yearly"},
            "published_at": ctx.rng.choice(ctx.dates).isoformat(),
        })
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")

def clean_wttj() -> pd.DataFrame:
    df = pd.read_json(_bronze("wttj/wttj_jobs.json"))
    comp = df["compensation"]
    out = pd.DataFrame()
    out["company"] = df["organization"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
    out["skill"] = df["profession"].apply(transforms.normalize_skill_label)
    out["country_iso2"] = df["office"].apply(
        lambda x: transforms.map_country_iso2(x.get("country")) if isinstance(x, dict) else None)
    out["min_salary_eur"] = comp.apply(lambda c: c.get("min") if isinstance(c, dict) else None)
    out["max_salary_eur"] = comp.apply(lambda c: c.get("max") if isinstance(c, dict) else None)
    out["salary_eur"] = out[["min_salary_eur", "max_salary_eur"]].mean(axis=1).round(2)
    out["date_posted"] = pd.to_datetime(df["published_at"], errors="coerce").dt.date.astype("string")
    out["source"] = "wttj"
    return out[SALARY_COLS]

# + 1 ligne dans REGISTRY :
SalarySource("wttj", "wttj/wttj_jobs.json", "json", generate_wttj, clean_wttj),
```

## Résultat observé (exécution réelle pendant le développement)

Après ce seul ajout, `python -m pipeline.run all` a propagé la source de bout en bout,
**sans aucune autre modification** :

| Indicateur | Avant (6 sources) | Après (+ wttj) |
|---|---|---|
| `d_source` (dimension) | 6 | **7** |
| `fact_job` (lignes) | 1 643 | **2 043** |
| Offres `wttj` dans le DWH | — | **400** |
| Endpoint `/dimensions/` | 6 sources | **7 sources** (wttj listée) |

> La plateforme **canonique** reste à **6 sources** ; `wttj` est conservé ici comme
> **exemple reproductible** de l'extensibilité.
> Le coût d'ajout = **2 fonctions + 1 ligne de registre**, zéro impact silver/gold/DWH/API.
