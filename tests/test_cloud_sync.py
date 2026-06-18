"""Test du pipeline cloud avec moto in-process (@mock_aws) : pas de Docker ni
d'émulateur HTTP — on valide que cloud_sync peuple bien S3 + DynamoDB."""

import boto3
from moto import mock_aws

from pipeline import cloud_sync, gold, silver, synthetic


@mock_aws
def test_cloud_sync_populates_s3_and_dynamodb():
    region = "eu-west-3"
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(
        Bucket=cloud_sync.BUCKET,
        CreateBucketConfiguration={"LocationConstraint": region},
    )
    ddb = boto3.client("dynamodb", region_name=region)
    ddb.create_table(
        TableName=cloud_sync.TABLE,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Produit le médaillon (gold) puis exécute le pipeline cloud
    synthetic.generate_all()
    silver.build_silver()
    gold.build_gold()
    n_obj = cloud_sync.upload_lake()
    n_ind = cloud_sync.publish_indicators()

    assert n_obj > 0
    assert n_ind > 0

    # S3 : objets présents, dont la couche gold
    listed = s3.list_objects_v2(Bucket=cloud_sync.BUCKET)
    assert listed["KeyCount"] == n_obj
    assert any(o["Key"].startswith("gold/") for o in listed["Contents"])

    # DynamoDB : indicateurs chauds écrits + forme attendue
    table = boto3.resource("dynamodb", region_name=region).Table(cloud_sync.TABLE)
    scan = table.scan()
    assert scan["Count"] == n_ind
    sample = scan["Items"][0]
    assert sample["pk"].startswith("country#")
    assert "median_salary_eur" in sample
