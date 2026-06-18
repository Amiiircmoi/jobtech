"""Modèles Django mappés sur le schéma en étoile PostgreSQL.

`managed = False` : le Data Warehouse est la propriété du pipeline ETL
(sql/create_dw.sql + package `pipeline`). L'API ne fait que LIRE ces tables ;
Django ne les crée ni ne les migre (évite la double-propriété du schéma).
Django ne gère que ses tables internes (auth, sessions, admin, token JWT).
"""

from django.db import models


class DateDim(models.Model):
    date_key = models.DateField(primary_key=True)
    day = models.SmallIntegerField()
    month = models.SmallIntegerField()
    quarter = models.SmallIntegerField()
    year = models.SmallIntegerField()
    day_week = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = "d_date"


class CountryDim(models.Model):
    id_country = models.AutoField(primary_key=True)
    iso2 = models.CharField(max_length=2, unique=True)
    country_name = models.TextField()
    region = models.TextField(null=True)
    monnaie_iso3 = models.CharField(max_length=3, null=True)

    class Meta:
        managed = False
        db_table = "d_country"


class SkillDim(models.Model):
    id_skill = models.AutoField(primary_key=True)
    tech_label = models.TextField()
    skill_group = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = "d_skill"


class SourceDim(models.Model):
    id_source = models.AutoField(primary_key=True)
    source_name = models.TextField()

    class Meta:
        managed = False
        db_table = "d_source"


class CompanyDim(models.Model):
    id_company = models.AutoField(primary_key=True)
    company_name = models.TextField()
    workforce_size = models.TextField(null=True)
    sector = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = "d_company"


class FactJob(models.Model):
    id_fact = models.AutoField(primary_key=True)
    date_key = models.ForeignKey(DateDim, db_column="date_key", on_delete=models.DO_NOTHING)
    country = models.ForeignKey(CountryDim, db_column="id_country", on_delete=models.DO_NOTHING)
    company = models.ForeignKey(CompanyDim, db_column="id_company", on_delete=models.DO_NOTHING)
    skill = models.ForeignKey(SkillDim, db_column="id_skill", on_delete=models.DO_NOTHING)
    source = models.ForeignKey(SourceDim, db_column="id_source", on_delete=models.DO_NOTHING)
    avg_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    min_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    job_count = models.IntegerField()

    class Meta:
        managed = False
        db_table = "fact_job"
