"""Lambda servant un indicateur salarial depuis DynamoDB (derrière API Gateway).

Service cloud en lecture NoSQL : GET /indicators?country=FR&skill=python
→ médiane/moyenne servies depuis la table d'indicateurs chauds.
"""

import decimal
import json
import os

import boto3

_ddb = boto3.resource("dynamodb")
_TABLE = os.environ["INDICATORS_TABLE"]


def _default(o):
    if isinstance(o, decimal.Decimal):
        return float(o)
    raise TypeError


def handler(event, _context):
    params = event.get("queryStringParameters") or {}
    country = (params.get("country") or "FR").upper()
    skill = (params.get("skill") or "python").lower()
    item = _ddb.Table(_TABLE).get_item(
        Key={"pk": f"country#{country}", "sk": f"skill#{skill}"}
    ).get("Item")
    return {
        "statusCode": 200 if item else 404,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(item or {"error": "indicator not found"}, default=_default),
    }
