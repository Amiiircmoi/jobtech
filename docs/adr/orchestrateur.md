# Décision — Orchestrateur de pipeline : **Dagster** (vs Airflow vs Prefect)

> Choisir l'outil qui ordonnance et **surveille** le pipeline médaillon, avec la
> meilleure observabilité des données pour le moindre coût d'exploitation.

## Besoin

Ordonnancer et **surveiller** le pipeline médaillon `bronze → silver → gold → DWH`
(durées, volumétries, taux d'échec, fraîcheur), rendre l'ajout de source trivial,
le tout avec un volume modeste (~3 k lignes bronze → 2 k faits) et une **lisibilité
maximale**. Pas de besoin de cluster.

## Critères de choix

| Critère | Poids | Pourquoi |
|---|---|---|
| Observabilité native (lineage, métadonnées, fraîcheur) | ⭐⭐⭐ | Sert directement le monitoring du pipeline |
| Adéquation au modèle **médaillon** (données, pas tâches) | ⭐⭐⭐ | Les couches = des *assets* versionnés et observables |
| Légèreté d'infra (pas de cluster) | ⭐⭐ | Coût/complexité d'exploitation |
| Courbe d'apprentissage / Python-natif | ⭐⭐ | Mise en place rapide |
| Ordonnanceur intégré (cron) | ⭐⭐ | Planification sans outil tiers |

## Comparatif

| | **Airflow** | **Prefect** | **Dagster** ✅ |
|---|---|---|---|
| Paradigme | Tâches (DAG d'opérateurs) | Flux/tâches Python | **Assets de données** (lineage 1ʳᵉ classe) |
| Observabilité données | Faible (orienté tâches) | Moyenne | **Forte** : catalogue, métadonnées de matérialisation, **freshness**, **asset checks** |
| Infra mini | Lourde (webserver + scheduler + metadata DB) | Légère (agent + API/cloud) | **Légère** (`dagster dev`, instance locale) |
| Ergonomie | Datée, verbeuse | Bonne | **Bonne**, UI moderne lisible en démo |
| Ordonnanceur | Oui (cron) | Oui | **Oui (cron)** |
| Right-sizing (pas de cluster) | ✔ mais surdimensionné | ✔ | ✔ |

## Décision retenue : **Dagster**

Parce que le projet est une **plateforme data en médaillon**, le modèle *software-defined
assets* de Dagster colle au besoin : chaque couche (`bronze`, `silver`, `gold`,
`warehouse`) est un **asset** dont Dagster trace nativement le **lineage**, la **durée**,
le **statut succès/échec**, et où l'on **émet en métadonnées** la volumétrie ; les
**asset checks** (intégrité FK, fraîcheur < 25 h) ajoutent des garde-fous qualité.
→ Le monitoring est obtenu *sans outillage tiers*. L'**ordonnanceur cron** intégré
(`ScheduleDefinition`, 06:00 quotidien) couvre la planification.

### Pourquoi pas Airflow
Standard du marché mais **orienté tâches** (pas données), **lourd** à exploiter
(webserver + scheduler + base de métadonnées) et **surdimensionné** pour ce volume.
On le cite comme la référence dont on a fait le *right-sizing*.

### Pourquoi pas Prefect
Excellent et léger, mais **orienté flux/tâches** : il faut outiller soi-même le
catalogue d'assets, le lineage et la fraîcheur que Dagster fournit *de base*. Pour un
récit « plateforme data » médaillon, Dagster est plus direct. (Aucun des deux n'impose
un cluster : le right-sizing est respecté dans les deux cas.)

## Preuve (exécution réelle)

`dagster asset materialize -m orchestration.definitions --select '*'` →
`bronze`(358 ms) → `silver`(417 ms) → `gold`(368 ms) → `warehouse`(436 ms),
asset checks `fact_integrity` et `warehouse_freshness` **passés**, `RUN_SUCCESS`.

## Limites & axes d'amélioration (recul)

- Courbe d'apprentissage initiale de Dagster supérieure à Prefect.
- **Non encore exploité** : `dagster-postgres` pour persister l'historique des runs
  hors SQLite local. → axe d'amélioration documenté.
- L'ordonnancement « production » (entrypoint Docker `sleep`) reste un *placeholder* ;
  la cible est ce planning Dagster.
