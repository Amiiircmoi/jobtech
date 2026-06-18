# Décision — Contrôle de version, conteneurisation, testing, CI/CD

> Industrialiser le projet : versionner, tester, conteneuriser et déployer de façon
> **reproductible et automatique**, sans usine à gaz.

## Besoin

Industrialiser jobtech : versionner, tester, conteneuriser et déployer de façon
**reproductible et automatique**, sans surcoût d'exploitation, pour un dépôt public.
Critère directeur : **lisibilité** + **coût/maintenance minimal**.

## Axes d'arbitrage

### 1. Contrôle de version — **Git + GitHub**
| Option | Pour | Contre | Retenu |
|---|---|---|---|
| **Git / GitHub** | standard de facto, PR, Actions intégrées, GHCR gratuit | — | ✅ |
| GitLab | CI intégrée puissante | second compte/écosystème, pas d'usage existant | ✗ |

Pratiques : branches + commits **convention** (`feat(...): …`), `.gitignore` strict
(données/binaires/secrets hors Git), historique lisible.

### 2. Conteneurisation — **Docker (+ docker compose)**
| Option | Pour | Contre | Retenu |
|---|---|---|---|
| **Docker / compose** | reproductible, 2 images (API gunicorn, ETL), `compose` = stack locale = stack CI | — | ✅ |
| Podman | rootless | moindre ubiquité, pas de gain ici | ✗ |
| Pas de conteneur | simple | non reproductible | ✗ |

Choix : **multi-stage minimal**, image API (gunicorn) + image ETL ; `docker-compose.yml`
(db + api + etl) est l'**artefact canonique** rejoué tel quel en CI.

### 3. Testing — **pytest (+ pytest-django, coverage, Pandera)**
| Option | Pour | Contre | Retenu |
|---|---|---|---|
| **pytest** | concis, fixtures, écosystème, `--cov` | — | ✅ |
| unittest | stdlib | verbeux, moins d'outillage | ✗ |

**Typologie de tests** réellement présente :
- **unitaires** (`transforms` : devises/ISO2/fourchettes) ;
- **qualité de données** (gate Pandera silver+gold) ;
- **intégration médaillon** (bronze→silver→gold) ;
- **idempotence DWH** (UPSERT micro-batch sans doublon) ;
- **contrat API** (endpoints, auth 200/401) ;
- **parité réel↔synthétique** (`ingest_real` mocké → schéma silver) ;
- **pipeline cloud** (moto in-process : S3 + DynamoDB peuplés).

Garde-fou CI : **couverture seuil 75 %** (`--cov-fail-under=75`).

### 4. CI/CD — **GitHub Actions (+ GHCR)**
| Option | Pour | Contre | Retenu |
|---|---|---|---|
| **GitHub Actions** | natif au dépôt, gratuit, services (Postgres), GHCR | — | ✅ |
| Jenkins | flexible | serveur à héberger/maintenir | ✗ |
| GitLab CI | puissant | hors écosystème | ✗ |

Pipeline (`.github/workflows/ci.yml`) = **4 jobs** : `quality` (ruff + ETL réel sur
service Postgres + pytest/couverture), `orchestration` (validation Dagster),
`docker` (build images + smoke `docker compose up` + `curl` endpoint = 200),
`publish` (push GHCR sur `main`).

## Pourquoi pas plus lourd (right-sizing)

Pas de Jenkins/ArgoCD/registry privé/k8s : volume modeste, dépôt public.
GitHub Actions + Docker + pytest couvrent le besoin avec un coût d'exploitation
quasi nul — cohérent avec le right-sizing du reste du projet (cf.
[`orchestrateur.md`](orchestrateur.md), et la veille « pas de Spark » côté traitement
distribué).

## Limites & recul

- **Pas de CD vers un environnement** (déploiement reste manuel via le kit `deploy/`).
- Pas de tests de charge en CI (latence mesurée hors CI, cf. `bench_latency.py`).
- Signature d'images / SBOM non mis en place (axe d'amélioration sécurité supply-chain).
