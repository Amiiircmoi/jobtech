"""Client Python minimal de l'API jobtech (intégration automatisée).

Ce client illustre l'**intégration programmatique** rendue possible par le contrat
OpenAPI (`openapi.yaml`). Il est volontairement mince et typé (dataclasses) ; un
client COMPLET s'obtient automatiquement depuis le schéma, sans écrire de code :

    # génération automatique d'un client typé depuis le schéma servi par l'API
    pipx run openapi-python-client generate --url http://localhost:8000/api/schema/
    # → paquet `jobtech_api_client/` (modèles + appels) prêt à l'emploi

Le présent fichier sert d'exemple lisible (et de preuve exécutable, cf. example.py)
sans dépendance de génération.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class SalaryStats:
    median: float | None
    p25: float | None
    p75: float | None
    avg: float | None
    sample_size: int


class JobtechClient:
    """Accès typé aux endpoints analytiques v1 (lecture publique, JWT optionnel)."""

    def __init__(self, base_url: str = "http://localhost:8000", token: str | None = None):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"

    def salary_stats(self, *, country=None, skill=None, source=None) -> SalaryStats:
        params = {k: v for k, v in dict(country=country, skill=skill, source=source).items() if v}
        r = self.s.get(f"{self.base}/api/v1/salary-stats/", params=params, timeout=15)
        r.raise_for_status()
        return SalaryStats(**r.json())

    def salary_cube(self, *, dimensions="country,skill", **filters) -> list[dict]:
        params = {"dimensions": dimensions, **{k: v for k, v in filters.items() if v}}
        r = self.s.get(f"{self.base}/api/v1/salary-cube/", params=params, timeout=15)
        r.raise_for_status()
        return r.json()["results"]

    def dimensions(self) -> dict:
        r = self.s.get(f"{self.base}/api/v1/dimensions/", timeout=15)
        r.raise_for_status()
        return r.json()
