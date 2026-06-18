# Décision — Quasi-temps réel / streaming

> Choix de traitement « frais » : micro-batch incrémental sur fenêtre, avec un
> prolongement cloud possible vers un vrai service temps réel.

## Constat honnête de l'existant

L'« ancien » quasi-temps réel était un `sleep 24h` dans `entrypoint.sh` — ce n'est
ni du streaming, ni du micro-batch. Le pipeline historique est un **batch full-refresh**
(régénère bronze→gold→DWH à chaque exécution). C'est correct au volume actuel mais
ne constitue pas un traitement incrémental.

## Right-sizing : pourquoi PAS un broker de streaming en local

Le marché de l'emploi n'est pas un flux continu : quelques centaines d'offres/jour,
pas d'évènements à la milliseconde. Déployer Kafka/Redpanda/Kinesis en local serait
disproportionné (coût/complexité >> bénéfice). On documente ce non-choix.

## Plan retenu

**(a) Micro-batch incrémental — la cible, réalisée avec Dagster.**
- Filtrer à l'ingestion les **offres « fraîches »** depuis un *watermark* (date
  `created` / `published_at` ou id max déjà vu), et n'**append**er que le nouveau en
  silver (au lieu d'un full-refresh).
- Ordonnancement **fréquent** (ex. toutes les 15 min) via un **schedule Dagster**
  dédié, avec **assets partitionnés par jour** + backfills.
- Le DWH étant déjà chargé en **UPSERT idempotent**, le micro-batch s'y intègre sans
  doublon. → fenêtre de traitement courte = micro-batch.

**(b) Vrai temps réel — prolongement cloud.**
- Un flux léger d'offres « fraîches » via **Amazon Kinesis** (ou Redpanda)
  → **Lambda** de transformation → écriture S3 silver + **DynamoDB** (indicateurs
  chauds servis par l'API). C'est là que le « temps réel au fil de l'eau » prend son
  sens (et reste *free-tier-friendly* en LocalStack puis AWS).

## Où c'est (ou sera) réalisé

| Brique | État |
|---|---|
| Micro-batch incrémental (watermark + schedule + partitions Dagster) | **Implémenté** (asset partitionné `fresh_offers` + UPSERT idempotent) |
| Streaming Kinesis→Lambda→DynamoDB (offres fraîches) | **Provisionné, non câblé** (stream + IAM prêts ; producteur à brancher) |

## Limites & recul

Le batch full-refresh reste disponible et assumé (volume faible). Le micro-batch
incrémental est en place (Dagster + UPSERT idempotent) ; le branchement d'un vrai
producteur Kinesis bout-en-bout est documenté comme **axe d'amélioration**.
