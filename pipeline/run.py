"""CLI d'orchestration du pipeline médaillon.

Usage :
    python -m pipeline.run all        # bronze → silver → gold → load (défaut)
    python -m pipeline.run bronze     # génère uniquement la couche bronze
    python -m pipeline.run silver
    python -m pipeline.run gold
    python -m pipeline.run load        # charge gold → PostgreSQL
    python -m pipeline.run manifest    # affiche les indicateurs du datalake
"""

import argparse
import time

from . import gold, lake, load_dw, silver, synthetic

STAGES = ["bronze", "silver", "gold", "load"]


def _run_stage(stage: str) -> None:
    t0 = time.perf_counter()
    if stage == "bronze":
        print("▶ BRONZE — génération synthétique (format natif des sources)")
        synthetic.generate_all()
    elif stage == "silver":
        print("▶ SILVER — nettoyage / typage / normalisation")
        silver.build_silver()
    elif stage == "gold":
        print("▶ GOLD — agrégats du schéma en étoile")
        gold.build_gold()
    elif stage == "load":
        print("▶ LOAD — chargement transactionnel vers PostgreSQL")
        counts = load_dw.load()
        for t, c in counts.items():
            print(f"    {t:<12} {c:>6} lignes")
    elif stage == "cloud":
        print("▶ CLOUD — sync S3 + indicateurs DynamoDB")
        from . import cloud_sync
        cloud_sync.main()
    print(f"  ⏱  {stage} terminé en {time.perf_counter() - t0:.2f}s\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline médaillon jobtech")
    parser.add_argument(
        "stage",
        nargs="?",
        default="all",
        choices=[*STAGES, "cloud", "all", "manifest"],
        help="étape à exécuter (défaut: all ; 'cloud' = sync S3/DynamoDB, requiert l'infra cloud)",
    )
    args = parser.parse_args()

    if args.stage == "manifest":
        lake.print_manifest()
        return

    stages = STAGES if args.stage == "all" else [args.stage]
    t0 = time.perf_counter()
    for stage in stages:
        _run_stage(stage)
    if args.stage == "all":
        print(f"✅ Pipeline complet en {time.perf_counter() - t0:.2f}s")
        lake.print_manifest()


if __name__ == "__main__":
    main()
