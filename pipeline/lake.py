"""Contrat du datalake médaillon : chemins par couche, écriture, et manifest.

Le manifest (data/manifest.json) maintient pour chaque jeu de données ses
indicateurs de fraîcheur (written_at) et de volumétrie (rows, bytes) pour
monitorer l'état du datalake.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import config

_LAYERS = {
    "bronze": config.BRONZE_DIR,
    "silver": config.SILVER_DIR,
    "gold": config.GOLD_DIR,
}


def layer_dir(layer: str):
    """Retourne (et crée) le répertoire d'une couche médaillon."""
    d = _LAYERS[layer]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_bytes(layer: str, relative_path: str, content: bytes, *, source: str, fmt: str) -> Path:
    """Écrit un fichier brut (bronze) et l'enregistre dans le manifest."""
    path = layer_dir(layer) / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    record(layer, source, rows=_count_records(content, fmt), bytes_=len(content), fmt=fmt)
    return path


def write_parquet(layer: str, name: str, df: pd.DataFrame, *, source: str | None = None) -> Path:
    """Écrit un DataFrame en Parquet (silver/gold) et met à jour le manifest."""
    path = layer_dir(layer) / f"{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    record(layer, source or name, rows=len(df), bytes_=path.stat().st_size, fmt="parquet")
    return path


def _count_records(content: bytes, fmt: str) -> int | None:
    """Estime un nombre d'enregistrements pour le manifest (best effort)."""
    try:
        if fmt == "json":
            data = json.loads(content)
            return len(data) if isinstance(data, list) else 1
        if fmt == "csv":
            # nombre de lignes - en-tête
            return max(content.count(b"\n") - 1, 0)
    except Exception:
        return None
    return None


def record(layer: str, dataset: str, *, rows, bytes_, fmt: str) -> None:
    """Met à jour l'entrée (layer, dataset) du manifest avec fraîcheur + volumétrie."""
    manifest = load_manifest()
    manifest.setdefault("layers", {}).setdefault(layer, {})[dataset] = {
        "rows": rows,
        "bytes": bytes_,
        "format": fmt,
        "written_at": _now_iso(),
    }
    manifest["updated_at"] = _now_iso()
    config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def load_manifest() -> dict:
    if config.MANIFEST_PATH.exists():
        return json.loads(config.MANIFEST_PATH.read_text())
    return {}


def print_manifest() -> None:
    """Affiche un récapitulatif lisible du manifest (fraîcheur/volumétrie)."""
    manifest = load_manifest()
    if not manifest:
        print("(manifest vide — lancer le pipeline)")
        return
    print(f"Datalake manifest — mis à jour {manifest.get('updated_at')}")
    for layer in ("bronze", "silver", "gold"):
        datasets = manifest.get("layers", {}).get(layer, {})
        if not datasets:
            continue
        total_rows = sum((d.get("rows") or 0) for d in datasets.values())
        print(f"\n[{layer.upper()}] {len(datasets)} jeu(x), {total_rows} lignes")
        for name, meta in sorted(datasets.items()):
            kb = (meta.get("bytes") or 0) / 1024
            print(f"  - {name:<22} {str(meta.get('rows')):>8} lignes  {kb:8.1f} Ko  {meta.get('format')}  @ {meta.get('written_at')}")
