"""Tests de contrat de l'API (forme des réponses + auth), sur un DWH semé.
Couvre les endpoints, l'authentification et le cube multidimensionnel."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


def test_dimensions_contract(seeded_dw, client):
    r = client.get("/api/v1/dimensions/")
    assert r.status_code == 200
    body = r.json()
    assert "FR" in body["countries"]
    assert "python" in body["skills"]
    assert "adzuna" in body["sources"]


def test_salary_stats_contract(seeded_dw, client):
    r = client.get("/api/v1/salary-stats/?country=FR&skill=python")
    assert r.status_code == 200
    body = r.json()
    assert {"median", "p25", "p75", "avg", "sample_size"} <= set(body)
    assert body["sample_size"] == 1
    assert body["median"] == pytest.approx(55000, rel=0.01)


def test_salary_cube_contract(seeded_dw, client):
    r = client.get("/api/v1/salary-cube/?dimensions=country,skill")
    assert r.status_code == 200
    results = r.json()["results"]
    assert results
    assert {"country", "skill", "avg_salary", "median_salary", "job_count"} <= set(results[0])


def test_jwt_obtain_then_use(seeded_dw, client):
    User.objects.create_user("u", "u@x.fr", "pw12345")
    tok = client.post("/api/v1/auth/token/", {"username": "u", "password": "pw12345"}, format="json")
    assert tok.status_code == 200
    assert "access" in tok.json()
