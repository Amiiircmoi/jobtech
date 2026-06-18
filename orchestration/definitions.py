"""Orchestration Dagster du pipeline médaillon jobtech.

Chaque couche médaillon est un **asset** Dagster ; les dépendances forment le DAG
bronze → silver → gold → warehouse. Dagster apporte :
  • l'ORDONNANCEUR (ScheduleDefinition cron)
  • le MONITORING : durée par asset, volumétrie, taux d'échec
    (durées et statut succès/échec tracés nativement par Dagster ; volumétries et
     fraîcheur émises en métadonnées de matérialisation ci-dessous)
  • des CONTRÔLES qualité (asset checks)

Lancer l'UI : `dagster dev -m orchestration.definitions`
Matérialiser en CLI : `dagster asset materialize -m orchestration.definitions --select '*'`
"""

import time
from datetime import UTC, date, datetime

import psycopg
from dagster import (
    AssetCheckResult,
    AssetExecutionContext,
    DailyPartitionsDefinition,
    Definitions,
    MaterializeResult,
    MetadataValue,
    ScheduleDefinition,
    asset,
    asset_check,
    build_schedule_from_partitioned_job,
    define_asset_job,
)

from pipeline import config, incremental, lake, load_dw, sources, synthetic
from pipeline import gold as gold_mod
from pipeline import silver as silver_mod


def _timed(fn):
    t0 = time.perf_counter()
    result = fn()
    return result, round(time.perf_counter() - t0, 3)


@asset(group_name="medallion", compute_kind="python",
       description="Ingestion bronze : sources synthétiques aux formats natifs (JSON/CSV).")
def bronze(context: AssetExecutionContext) -> MaterializeResult:
    paths, dur = _timed(synthetic.generate_all)
    datasets = lake.load_manifest().get("layers", {}).get("bronze", {})
    rows = sum((m.get("rows") or 0) for m in datasets.values())
    context.log.info(f"bronze: {len(paths)} jeux, {rows} lignes en {dur}s")
    return MaterializeResult(metadata={
        "datasets": len(paths),
        "rows": rows,
        "duration_s": dur,
        "salary_sources": MetadataValue.json(sources.salary_source_names()),
    })


@asset(deps=[bronze], group_name="medallion", compute_kind="pandas",
       description="Nettoyage / typage / normalisation (silver, Parquet).")
def silver(context: AssetExecutionContext) -> MaterializeResult:
    out, dur = _timed(silver_mod.build_silver)
    rows = sum(len(df) for df in out.values())
    context.log.info(f"silver: {len(out)} jeux, {rows} lignes en {dur}s")
    return MaterializeResult(metadata={"datasets": len(out), "rows": rows, "duration_s": dur})


@asset(deps=[silver], group_name="medallion", compute_kind="pandas",
       description="Agrégats du schéma en étoile (gold : dimensions + faits).")
def gold(context: AssetExecutionContext) -> MaterializeResult:
    res, dur = _timed(gold_mod.build_gold)
    dims = {k: len(v) for k, v in res.items() if k.startswith("dim_")}
    context.log.info(f"gold: fact={len(res['fact_job'])}, dims={dims} en {dur}s")
    return MaterializeResult(metadata={
        "fact_rows": len(res["fact_job"]),
        "dimensions": MetadataValue.json(dims),
        "duration_s": dur,
    })


@asset(deps=[gold], group_name="medallion", compute_kind="postgres",
       description="Chargement transactionnel idempotent vers le Data Warehouse PostgreSQL.")
def warehouse(context: AssetExecutionContext) -> MaterializeResult:
    counts, dur = _timed(load_dw.load)
    context.log.info(f"warehouse: {counts} en {dur}s")
    return MaterializeResult(metadata={
        **{f"dw_{k}": v for k, v in counts.items()},
        "duration_s": dur,
    })


# ── Contrôles qualité (asset checks) ──────────────────────────────────────
@asset_check(asset=warehouse, description="Table de faits non vide et sans dimension orpheline.")
def fact_integrity(context) -> AssetCheckResult:
    with psycopg.connect(config.DATABASE_URL) as conn:
        n = conn.execute("SELECT count(*) FROM fact_job").fetchone()[0]
        orphans = conn.execute(
            "SELECT count(*) FROM fact_job f "
            "LEFT JOIN d_country c ON c.id_country = f.id_country WHERE c.id_country IS NULL"
        ).fetchone()[0]
    return AssetCheckResult(
        passed=bool(n > 0 and orphans == 0),
        metadata={"fact_rows": n, "orphans": orphans},
    )


@asset_check(asset=warehouse, description="Fraîcheur du DW : dernière matérialisation < 25h.")
def warehouse_freshness(context) -> AssetCheckResult:
    updated = lake.load_manifest().get("updated_at")
    age_h = None
    if updated:
        delta = datetime.now(UTC) - datetime.fromisoformat(updated)
        age_h = round(delta.total_seconds() / 3600, 2)
    return AssetCheckResult(
        passed=bool(age_h is not None and age_h < 25),
        metadata={"age_hours": age_h, "updated_at": updated or "n/a"},
    )


# ── Micro-batch incrémental : asset partitionné par jour ───────────────────
daily_partitions = DailyPartitionsDefinition(start_date="2026-06-16")


@asset(
    partitions_def=daily_partitions,
    group_name="micro_batch",
    compute_kind="postgres",
    description="Micro-batch : ingère les offres fraîches d'UNE journée (UPSERT, sans full-refresh).",
)
def fresh_offers(context: AssetExecutionContext) -> MaterializeResult:
    res = incremental.run_micro_batch(date.fromisoformat(context.partition_key))
    return MaterializeResult(metadata={
        "batch_date": res["batch_date"],
        "rows_ingested": res["rows"],
        "fact_total": res["fact_job"],
    })


# ── Jobs + ordonnanceurs ───────────────────────────────────────────────────
medallion_job = define_asset_job("medallion_job", selection=["bronze", "silver", "gold", "warehouse"])
incremental_job = define_asset_job("incremental_job", selection=[fresh_offers], partitions_def=daily_partitions)

daily_medallion = ScheduleDefinition(           # batch full-refresh quotidien
    job=medallion_job, cron_schedule="0 6 * * *", name="daily_medallion",
)
daily_micro_batch = build_schedule_from_partitioned_job(  # micro-batch fenêtré
    incremental_job, name="daily_micro_batch",
)

defs = Definitions(
    assets=[bronze, silver, gold, warehouse, fresh_offers],
    asset_checks=[fact_integrity, warehouse_freshness],
    jobs=[medallion_job, incremental_job],
    schedules=[daily_medallion, daily_micro_batch],
)
