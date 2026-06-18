"""Pipeline cloud : pousse le datalake médaillon vers S3 et publie les indicateurs
chauds dans DynamoDB.

Endpoint-aware : `AWS_ENDPOINT_URL` pointe LocalStack en local ; vide sur AWS réel
(le code est identique). Lancé après le pipeline médaillon (`pipeline.run all`).
"""

import decimal
import os

import boto3
import pandas as pd

from . import config

ENDPOINT = os.getenv("AWS_ENDPOINT_URL") or None  # LocalStack en local, None sur AWS réel
REGION = os.getenv("AWS_REGION", "eu-west-3")
BUCKET = os.getenv("S3_BUCKET", "jobtech-datalake-local")
TABLE = os.getenv("DDB_TABLE", "jobtech-indicators-local")


def _client(svc):
    return boto3.client(svc, region_name=REGION, endpoint_url=ENDPOINT)


def _resource(svc):
    return boto3.resource(svc, region_name=REGION, endpoint_url=ENDPOINT)


def upload_lake() -> int:
    """Réplique les couches bronze/silver/gold locales vers le bucket S3 (préfixes)."""
    s3 = _client("s3")
    n = 0
    for layer in ("bronze", "silver", "gold"):
        layer_dir = config.DATA_DIR / layer
        if not layer_dir.exists():
            continue
        for f in layer_dir.rglob("*"):
            if f.is_file():
                s3.upload_file(str(f), BUCKET, f"{layer}/{f.relative_to(layer_dir).as_posix()}")
                n += 1
    print(f"S3 ← {n} objets dans s3://{BUCKET} (bronze/silver/gold)")
    return n


def publish_indicators() -> int:
    """Calcule les indicateurs chauds (médiane/moyenne/volume par pays×skill) → DynamoDB."""
    fact = pd.read_parquet(config.GOLD_DIR / "fact_job.parquet")
    agg = (
        fact.groupby(["country_iso2", "skill"])
        .agg(median=("avg_salary", "median"), avg=("avg_salary", "mean"), volume=("job_count", "sum"))
        .reset_index()
    )
    table = _resource("dynamodb").Table(TABLE)
    with table.batch_writer() as bw:
        for r in agg.itertuples(index=False):
            bw.put_item(Item={
                "pk": f"country#{r.country_iso2}",
                "sk": f"skill#{r.skill}",
                "median_salary_eur": decimal.Decimal(str(round(r.median, 2))),
                "avg_salary_eur": decimal.Decimal(str(round(r.avg, 2))),
                "volume": int(r.volume),
            })
    print(f"DynamoDB ← {len(agg)} indicateurs dans {TABLE}")
    return len(agg)


def main() -> None:
    upload_lake()
    publish_indicators()


if __name__ == "__main__":
    main()
