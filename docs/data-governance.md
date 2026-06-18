# Gouvernance des données & RGPD

> Plateforme d'indicateurs **agrégés et anonymes** sur le marché de l'emploi Tech.
> Principe directeur RGPD : **aucune donnée personnelle** n'est nécessaire à la
> finalité (statistiques salariales/volumes par pays/compétence/source).

## 1. Provenance, licences & base légale des 6 sources

| Source | Type | Accès | Base légale / cadre | Donnée personnelle ? |
|---|---|---|---|---|
| **Adzuna** | Offres d'emploi | API REST (clé) | CGU API Adzuna ; usage analytique | Non (offres, pas de personnes) |
| **Stack Overflow Survey** | Enquête développeurs | Jeu **Open Data** publié (ODbL) | Licence ouverte de l'éditeur | Anonymisé à la source |
| **GitHub Trending** | Dépôts publics | Scraping HTML public | Données publiques ; respect `robots.txt` | Non (dépôts) |
| **Google Trends** | Indices de popularité | `pytrends` (API non off.) | Indices agrégés publics | Non |
| **Indeed** | Offres d'emploi | Scraping (référence, non activé) | CGU ; usage mesuré | Non (offres) |
| **Glassdoor** | Salaires déclarés | Scraping (référence, non activé) | CGU ; usage mesuré | Agrégé/anonyme |

**Démo = données synthétiques** (Faker) → **zéro donnée réelle, zéro PII**.

## 2. Minimisation

- On ne conserve que les **colonnes utiles aux indicateurs** : pays (ISO2),
  compétence, source, entreprise (nom public), salaire (EUR), date, volume.
- **Aucun identifiant personnel** (pas de nom de personne, email, profil).
- Les salaires sont **agrégés** au grain *date × pays × compétence × source ×
  entreprise* dès la couche gold (pas d'observation individuelle exposée par l'API).

## 3. Rétention par couche (politique)

| Couche | Contenu | Rétention cible | Justification |
|---|---|---|---|
| **bronze** | dumps bruts | **30 jours** glissants | rejeu/debug court terme ; purge ensuite (lifecycle S3 côté cloud) |
| **silver** | nettoyé/typé | 90 jours | fenêtre d'analyse récente |
| **gold / DWH** | agrégats anonymes | **conservation longue** | aucune PII → pas de limite RGPD |
| archivage | gold ancien | Glacier (cloud) | coût/froid |

Côté cloud : la rétention bronze→IA→Glacier est **implémentée par lifecycle S3**
(traduction technique de la politique de conservation).

## 4. Lignage des données (traçabilité)

```
source (CGU/licence) → bronze (immuable, daté) → silver (transformé, validé Pandera)
   → gold (agrégé, étoile) → DWH PostgreSQL → API (indicateurs)
```
- Chaque couche est **datée** et **mesurée** (`data/manifest.json` : fraîcheur + volumétrie).
- Dagster trace le **lineage** des assets (qui produit quoi) et l'historique des runs.
- Les transformations sont **versionnées** (Git) et **testées** (gate qualité).

## 5. Sécurité (rappel, détaillée côté cloud)

- Secrets hors code (`.env` / variables d'environnement) ; clés d'API jamais commitées.
- Chiffrement **at-rest** (KMS sur S3/DynamoDB) + **in-transit** (TLS) dans le cloud.
- **IAM least-privilege** par service (cloud).

## 6. Limites & recul

- Indeed/Glassdoor : scraping soumis aux CGU et au `robots.txt` — **non activés** en
  production (fragiles, zone grise juridique) ; conservés en référence. Un accès
  conforme passerait par une **API officielle/partenariat** (hors périmètre).
- Pas de DPO ni de registre de traitement formel (projet personnel) ; la
  démarche de **minimisation + anonymisation** est toutefois appliquée par conception.
