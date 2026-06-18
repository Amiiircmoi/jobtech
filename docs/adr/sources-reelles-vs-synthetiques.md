# Décision — Sources réelles vs données synthétiques (+ RGPD)

> Pourquoi le dépôt s'appuie sur des données synthétiques déterministes pour la démo,
> tout en gardant les connecteurs d'ingestion réelle — avec les implications RGPD
> (base légale, minimisation, rétention).

## Les 6 sources réelles (et leur ingestion)

| Source | Format natif | Méthode réelle | Robustesse | Wiring `ingest_real.py` |
|---|---|---|---|---|
| **Adzuna** | JSON (API REST) | API officielle (clés via env) | Élevée | ✅ `fetch_adzuna` (aligné schéma bronze) |
| **Stack Overflow Survey** | CSV (ZIP) | Téléchargement annuel | Élevée | ✅ `download_so_survey` |
| **GitHub Trending** | HTML → JSON | Scraping HTML public | Moyenne | ✅ `fetch_github_trending` |
| **Google Trends** | CSV (lib) | `pytrends` | Moyenne | ✅ `fetch_google_trends` |
| **Indeed** | HTML → CSV | Selenium (anti-bot, captcha) | **Fragile** | ⚠️ référence (`scrape_indeed`, non activé) |
| **Glassdoor** | HTML → CSV | Selenium (anti-bot) | **Fragile** | ⚠️ référence (non activé) |

→ **4 sources sur 6 sont réellement ingérables** sans navigateur (API / lib /
téléchargement) ; les 2 restantes (Indeed, Glassdoor) sont **conservées comme
référence** du parcours de scraping (DOM + captcha) mais non activées car fragiles.

## La clé : un schéma bronze identique réel ↔ synthétique

Le générateur synthétique (`pipeline/sources.py`) produit, pour chaque source, le
**même schéma natif** que l'ingestion réelle. Conséquence : **les mêmes nettoyeurs
silver tournent sur les deux** (réel ou synthétique). On peut donc :
- **développer/démontrer** sur le synthétique (déterministe, rejouable, CI-friendly) ;
- **brancher le réel** sans changer une ligne de silver/gold/DWH.

C'est ce qui rend l'affirmation *« 6 sources réelles, démo synthétique reproductible »*
défendable : la chaîne de transformation est **prouvée identique** sur les deux entrées.

## Pourquoi la démo est synthétique (fiabilité + reproductibilité)

- Scrapers anti-bot non rejouables → risque de démo cassée.
- API à quotas/clés → dépendance externe au moment de la démo.
- Le synthétique (seed figée) garantit une **démo et une CI 100 % reproductibles**.

## RGPD / sécurité

- **Données synthétiques = zéro donnée personnelle** : entreprises (Faker) et montants
  sont **fictifs**. Aucune PII n'est générée, stockée ni traitée.
- **Données réelles** (si ingestion activée) : on ne conserve que des **offres et
  salaires agrégés/anonymes** — pas de personnes, pas d'identifiants personnels.
- **Base légale** : pages publiques / API sous CGU ; respect des `robots.txt` dans la
  mesure du possible ; pas de revente.
- **Minimisation & rétention** : seules les colonnes utiles aux indicateurs sont
  conservées (silver), bronze brut purgeable ; rétention à définir par couche.
- **Secrets** : clés d'API hors code (`.env` / variables d'environnement).

## Limites & recul

Indeed/Glassdoor non activés (anti-bot) — un proxy/API tierce payante serait
nécessaire pour les fiabiliser : **hors périmètre** (coût), documenté comme limite.
