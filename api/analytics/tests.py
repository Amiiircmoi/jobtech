"""Smoke tests de l'API (sans dépendre du Data Warehouse, tables managed=False).

La suite complète (requêtes sur le DW peuplé) est ajoutée en Phase 4 avec un
chargement du schéma étoile dans la base de test.
"""

from rest_framework.test import APITestCase


class AuthSmokeTest(APITestCase):
    def test_openapi_schema_available(self):
        """La doc OpenAPI est générée et servie."""
        assert self.client.get("/api/schema/").status_code == 200

    def test_jwt_rejects_bad_credentials(self):
        """L'auth JWT refuse des identifiants invalides."""
        resp = self.client.post(
            "/api/v1/auth/token/",
            {"username": "nobody", "password": "wrong"},
            format="json",
        )
        assert resp.status_code == 401
