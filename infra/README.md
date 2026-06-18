# Infrastructure cloud — Terraform

Infrastructure-as-code de jobtech sur AWS. **Code AWS standard** : le même Terraform
cible le vrai AWS ou un émulateur local (`var.aws_endpoint_url`), sans aucune
dépendance émulateur dans le code.

## Modules

| Module | Ressources |
|---|---|
| `lake` | S3 (versioning, **lifecycle** bronze→Glacier / silver,gold→IA, **chiffrement KMS**, **public access block**, **policy TLS-only**, réplication optionnelle) |
| `serving` | DynamoDB (on-demand, **chiffré KMS**, point-in-time recovery) — service des indicateurs « chauds » (NoSQL) |
| `pipelines` | Kinesis (flux temps réel, **provisionné non câblé**), Lambda (service indicateurs), API Gateway HTTP, **IAM least-privilege**, CloudWatch Logs |
| `relational` | **Glue Data Catalog + Athena** (schéma relationnel SQL serverless sur `gold/fact_job/`) — **gaté** `enable_relational` (non émulé par LocalStack Community) |

> **Kinesis** : le stream + les droits IAM existent (primitive temps réel), mais **aucun
> producteur ni `event_source_mapping`** ne l'alimente encore — la Lambda est déclenchée
> par API Gateway. Le câblage bout-en-bout est un chantier ultérieur.

Sur AWS réel s'ajoute le **dashboard de coûts** (Cost Explorer / Budgets) — non émulable
en local. Le module `relational` (Glue/Athena) est **codé et `validate`-clean** ;
son **apply** se fait sur AWS réel (Glue/Athena non émulés par LocalStack Community).

## Sécurité (matrice de flux)

- **At-rest** : KMS sur S3 (SSE-KMS + bucket key) et DynamoDB.
- **In-transit** : policy S3 **refusant tout accès non-TLS** (`aws:SecureTransport=false` → Deny).
- **IAM least-privilege** : rôle Lambda limité (GetItem DynamoDB + read Kinesis + logs).
- **Rétention** : lifecycle bronze 30 j → Glacier → expiration 90 j (cf. [`../docs/data-governance.md`](../docs/data-governance.md)).

## FinOps

- `default_tags` (`Project`, `Env`, `ManagedBy`) sur **toutes** les ressources → ventilation des coûts.
- Tout en **on-demand / pay-per-use** (S3, DynamoDB PAY_PER_REQUEST, Lambda, Kinesis 1 shard) → coût ≈ 0 au repos.

## Exécution

### Validation (sans cloud)
```bash
terraform init && terraform validate && terraform fmt -check -recursive
```

### Local — émulateur AWS (LocalStack)
**`terraform apply` a été exécuté sur LocalStack** : 20 ressources créées
(S3/KMS/DynamoDB/Kinesis/Lambda/IAM/CloudWatch/API GW), datalake peuplé et
**bout-en-bout `GET /indicators` → API GW → Lambda → DynamoDB = HTTP 200**
(reproductible au centime via le pipeline déterministe). En parallèle, le **code
applicatif cloud** (`pipeline/cloud_sync.py`) est aussi testé **en CI** via **moto
in-process** (`tests/test_cloud_sync.py`, `@mock_aws`, sans Docker).

```bash
LOCALSTACK_AUTH_TOKEN=... localstack start -d
tflocal apply        # tflocal injecte les endpoints LocalStack
python -m pipeline.run all && AWS_ENDPOINT_URL=http://localhost:4566 python -m pipeline.run cloud
```
> Non émulés par LocalStack Community → réservés à AWS réel : **Glue/Athena** (module
> `relational`, codé + `validate`-clean), lifecycle/réplication S3 réels, dashboard de coûts.

### AWS réel
```bash
cp terraform.tfvars.example terraform.tfvars   # name_suffix="prod", enable_replication=true
terraform apply                                 # aws_endpoint_url vide → vrai AWS
AWS_REGION=eu-west-3 python -m pipeline.run cloud   # peuple S3 + DynamoDB
```

## État de validation (vérifié 2026-06-17)

| Élément | Local | AWS réel |
|---|---|---|
| `terraform validate` (**4 modules** : lake, serving, pipelines, relational) | ✅ | ✅ attendu |
| Code pipeline cloud (S3 + DynamoDB) | ✅ moto in-process (test CI) | ✅ attendu |
| `terraform apply` (création réelle) | ✅ **LocalStack** (20 ressources, HTTP 200 bout-en-bout) | ⏳ apply autoritaire |
| Kinesis bout-en-bout (producteur + mapping) | ⚠️ **non câblé** | ⏳ |
| Glue/Athena (`relational`) | code ✅ `validate`-clean (non émulé) | ⏳ apply |
| Dashboard coûts FinOps | — (non émulable) | ⏳ à faire |
