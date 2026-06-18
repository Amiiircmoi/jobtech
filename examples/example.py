"""Exemple exécutable du client jobtech.

Usage : API lancée + DW chargé, puis :
    python examples/example.py [BASE_URL]
"""

import sys

from jobtech_client import JobtechClient

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
api = JobtechClient(base)

dims = api.dimensions()
print(f"dimensions : {len(dims['countries'])} pays · {len(dims['skills'])} skills · {len(dims['sources'])} sources")

stats = api.salary_stats(country="FR", skill="python")
print(f"FR/python  → médiane {stats.median} € · p25 {stats.p25} · p75 {stats.p75} · n={stats.sample_size}")

cube = api.salary_cube(dimensions="country,skill", source="adzuna")
print(f"cube country×skill (adzuna) : {len(cube)} cellules, ex. {cube[0]}")
