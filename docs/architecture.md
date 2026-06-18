# Architecture jobtech

Plateforme data qui cartographie le marché de l'emploi Tech : datalake médaillon +
Data Warehouse en étoile (PostgreSQL) + API REST d'indicateurs, orchestrée par Dagster
et intégrée en CI, avec une couche cloud (LocalStack → AWS).

---

## 1. Flux de données (médaillon → DWH → API)

```mermaid
flowchart LR
  subgraph SRC["6 sources hétérogènes"]
    direction TB
    A["Adzuna · JSON"]
    I["Indeed · CSV"]
    G["Glassdoor · CSV"]
    S["SO Survey · CSV"]
    H["GitHub · JSON"]
    T["Google Trends · CSV"]
  end

  SRC --> BR["BRONZE<br/>dumps bruts (format natif)"]
  BR --> SI["SILVER<br/>nettoyé/typé/normalisé · Parquet"]
  SI --> GO["GOLD<br/>dimensions + table de faits"]
  GO --> DW[("PostgreSQL<br/>schéma en étoile")]
  DW --> API["Django REST · /api/v1<br/>JWT · quotas · Swagger"]
  API --> CONS["Indicateurs<br/>médiane · cube · séries"]

  DAG{{"Dagster<br/>assets · cron · checks"}} -. orchestre .-> BR
  DAG -. orchestre .-> SI
  DAG -. orchestre .-> GO
  DAG -. orchestre .-> DW
  MAN[/"manifest.json<br/>fraîcheur + volumétrie"/] -. monitore .-> SI

  CI["GitHub Actions<br/>lint · tests · build · compose"] -. valide .-> API
```

**Transformations clés (silver)** : normalisation des devises → EUR, mapping pays →
ISO2 (`pycountry`, mémoïsé), parsing de fourchettes de salaire, éclatement
multi-compétences. **Contrat de données** explicite et unique entre couches.

---

## 2. Modèle dimensionnel — schéma en étoile (MCD/MLD)

```mermaid
erDiagram
  d_date    ||--o{ fact_job : "date_key"
  d_country ||--o{ fact_job : "id_country"
  d_company ||--o{ fact_job : "id_company"
  d_skill   ||--o{ fact_job : "id_skill"
  d_source  ||--o{ fact_job : "id_source"

  d_date {
    date     date_key PK
    smallint day
    smallint month
    smallint quarter
    smallint year
    smallint day_week
  }
  d_country {
    serial id_country PK
    char   iso2 UK
    text   country_name
    text   region
    char   monnaie_iso3
  }
  d_company {
    serial id_company PK
    text   company_name UK
    text   workforce_size
    text   sector
  }
  d_skill {
    serial id_skill PK
    text   tech_label UK
    text   skill_group
  }
  d_source {
    serial id_source PK
    text   source_name UK
  }
  fact_job {
    bigserial id_fact PK
    date      date_key FK
    int       id_country FK
    int       id_company FK
    int       id_skill FK
    int       id_source FK
    numeric   avg_salary
    numeric   min_salary
    numeric   max_salary
    int       job_count
  }
```

**Contraintes d'intégrité** : PK/FK sur toutes les dimensions ; `UNIQUE`
de grain `(date_key, id_country, id_company, id_skill, id_source)` permettant l'UPSERT
idempotent ; `CHECK (min_salary <= max_salary)` et `CHECK (job_count >= 0)`.
**MLD** : types PostgreSQL réels (`SERIAL`, `NUMERIC(12,2)`, `CHAR(2)`), index sur les
FK de la table de faits pour l'accès analytique.

---

## 3. Architecture technique courante

```mermaid
flowchart TB
  subgraph DEV["Poste / CI"]
    PIPE["pipeline/ (package ETL)<br/>sources · silver · gold · load_dw"]
    ORCH["orchestration/<br/>Dagster definitions"]
    TEST["tests + ruff + pytest"]
  end

  subgraph RUN["docker-compose"]
    DBC[("service db<br/>postgres:16")]
    APIC["service api<br/>gunicorn + Django REST"]
    ETLC["service etl<br/>pipeline médaillon"]
  end

  PIPE --> ETLC
  ORCH -. planifie .-> PIPE
  ETLC --> DBC
  APIC --> DBC
  TEST -. CI .-> RUN

  subgraph CLOUD["Cloud (LocalStack → AWS)"]
    S3["S3 médaillon + tiers archivage"]
    DDB["DynamoDB (indicateurs chauds)"]
    LBD["Lambda / Glue"]
  end
  RUN -. miroir cloud .-> CLOUD
```

**Cible de stockage unique** : PostgreSQL (DW étoile + lecture API). **Secrets** hors
code (`django-environ` + `.env`). **Images** : `api/Dockerfile` (gunicorn) et
`Dockerfile` (ETL). **Orchestration** : Dagster (assets + cron + asset checks).
**CI** : GitHub Actions (lint, tests, exécution ETL, build images, smoke
`docker compose up`).

---

## 4. Architecture cloud + matrice de flux sécurisés

```mermaid
flowchart LR
  GOLD["gold/ Parquet (local)"] -->|cloud_sync| S3[("S3 datalake<br/>bronze/silver/gold<br/>versioning + lifecycle + KMS")]
  S3 -->|crawler| GLUE["Glue Catalog + Athena<br/>(schéma relationnel)"]
  GOLD -->|cloud_sync| DDB[("DynamoDB<br/>indicateurs chauds")]
  KIN["Kinesis<br/>offres fraîches<br/>(provisionné, NON câblé)"] -. flux à activer .-> LBD["Lambda<br/>indicator_api"]
  DDB --> LBD --> APIGW["API Gateway HTTP<br/>GET /indicators"]
  S3 -. réplication .-> S3R[("S3 réplica")]
  KMS["KMS"] -. chiffre .-> S3 & DDB
  IAM["IAM least-privilege"] -. autorise .-> LBD
  CW["CloudWatch Logs"] -. journalise .-> LBD
  TAGS["Cost tags + on-demand"] -. FinOps .-> S3 & DDB & LBD
```

### Matrice de flux sécurisés

| Flux | Chiffrement transit | Chiffrement repos | Contrôle d'accès |
|---|---|---|---|
| client → API Gateway | TLS (HTTPS) | — | public lecture (indicateurs anonymes) |
| Lambda → DynamoDB | TLS interne AWS | KMS (table) | rôle IAM : `GetItem`/`Query` **uniquement** |
| Lambda → CloudWatch | TLS interne AWS | — | rôle IAM : `PutLogEvents` |
| cloud_sync → S3 | **TLS imposé** (policy `Deny aws:SecureTransport=false`) | SSE-KMS + bucket key | accès public entièrement bloqué |
| Kinesis → Lambda *(non câblé)* | TLS interne AWS | chiffrement Kinesis | rôle IAM : `GetRecords` **(droits prêts, flux à activer)** |
| S3 → S3 réplica | TLS interne AWS | SSE-KMS | rôle de réplication dédié |

> ⚠️ **Kinesis = primitive provisionnée, NON câblée.** Le stream et les droits IAM
> `GetRecords` existent (primitive temps réel en place), mais **aucun producteur**
> (`put_record`) ni **`event_source_mapping`** ne l'alimente encore : la Lambda est
> déclenchée par **API Gateway** (lecture DynamoDB), pas par Kinesis. Le branchement
> bout-en-bout (producteur + mapping + log) est un **axe d'amélioration**.

**Rétention RGPD** (lifecycle S3) : bronze 30 j → Glacier → expiration 90 j ; silver/gold → IA.
Détail : [data-governance.md](data-governance.md) · IaC : [`infra/`](../infra/README.md).

> État honnête (vérifié 2026-06-17) : IaC `terraform validate`-clean (lake, serving,
> pipelines, **relational** Glue/Athena) ; **`terraform apply` exécuté sur LocalStack**
> (20 ressources S3/KMS/DynamoDB/Kinesis/Lambda/IAM/API GW, bout-en-bout API GW→Lambda→
> DynamoDB **HTTP 200**) ; pipeline cloud aussi testé en CI via moto in-process.
> Restent **sur AWS réel** : apply autoritaire, **Glue/Athena** (code écrit +
> `validate`, apply réel), dashboard de coûts, réplication/lifecycle réels.
