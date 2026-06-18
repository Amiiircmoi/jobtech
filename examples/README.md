# Client API & intégration automatisée

L'API expose un **contrat OpenAPI 3** (`/api/schema/`, drf-spectacular) qui rend
l'intégration **automatisable** : un client typé se génère sans écrire de code.

## Artefacts

| Fichier | Rôle |
|---|---|
| `openapi.yaml` | schéma OpenAPI 3 exporté de l'API (`GET /api/schema/`) — le **contrat** |
| `jobtech_client.py` | client Python minimal, typé (dataclasses) — exemple lisible |
| `example.py` | **preuve exécutable** : appelle l'API live et imprime les indicateurs |

## Génération automatique d'un client complet (1 commande)

Depuis le schéma servi par l'API, sans écrire de code :

```bash
pipx run openapi-python-client generate --url http://localhost:8000/api/schema/
# → paquet `jobtech_api_client/` (modèles Pydantic + appels typés) prêt à l'emploi
```

(Autres cibles possibles depuis le même contrat : `openapi-generator` pour
TypeScript/Java/Go, Postman, etc.)

## Exemple (sortie réelle, mesuré le 2026-06-17)

```
$ python examples/example.py http://127.0.0.1:8009
dimensions : 9 pays · 12 skills · 6 sources
FR/python  → médiane 55605.415 € · p25 49375.0 · p75 64074.18 · n=12
cube country×skill (adzuna) : 50 cellules, ex. {'country': 'AU', 'skill': 'aws', ...}
```

> Statut honnête : le **contrat** (OpenAPI) + le **client minimal** + l'**exemple
> exécutable** sont fournis ; la génération d'un client complet est une **commande
> standard** documentée ci-dessus (outil non ajouté aux dépendances du projet).
