"""Fixtures pytest partagées.

`seeded_dw` : comme les modèles du DWH sont `managed=False` (le schéma appartient
au pipeline), Django ne les crée pas dans la base de test. Cette fixture applique
le DDL de l'étoile + sème quelques lignes, pour tester les endpoints qui lisent le DWH.
"""

import re

import pytest


@pytest.fixture
def seeded_dw(db):
    from django.db import connection

    from pipeline import config

    sql = re.sub(r"--[^\n]*", "", config.DDL_PATH.read_text())
    with connection.cursor() as cur:
        for stmt in (s.strip() for s in sql.split(";")):
            if stmt:
                cur.execute(stmt)
        cur.execute("INSERT INTO d_date VALUES ('2026-06-01',1,6,2,2026,0) ON CONFLICT DO NOTHING")
        cur.execute(
            "INSERT INTO d_country (iso2,country_name,region,monnaie_iso3) "
            "VALUES ('FR','France','Europe','EUR') ON CONFLICT DO NOTHING"
        )
        cur.execute("INSERT INTO d_skill (tech_label,skill_group) VALUES ('python','language') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO d_source (source_name) VALUES ('adzuna') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO d_company (company_name) VALUES ('ACME') ON CONFLICT DO NOTHING")
        cur.execute(
            """
            INSERT INTO fact_job
              (date_key,id_country,id_company,id_skill,id_source,avg_salary,min_salary,max_salary,job_count)
            SELECT '2026-06-01', c.id_country, co.id_company, s.id_skill, so.id_source, 55000, 50000, 60000, 3
            FROM d_country c, d_company co, d_skill s, d_source so
            WHERE c.iso2='FR' AND co.company_name='ACME' AND s.tech_label='python' AND so.source_name='adzuna'
            ON CONFLICT DO NOTHING
            """
        )
