from rest_framework import serializers


class SalaryDailySerializer(serializers.Serializer):
    """Point d'une série temporelle de salaire moyen."""

    date = serializers.DateField()
    avg_salary = serializers.DecimalField(max_digits=12, decimal_places=2)
    job_count = serializers.IntegerField()


class SalaryStatsSerializer(serializers.Serializer):
    """Statistiques de distribution salariale (médiane / quartiles)."""

    median = serializers.FloatField(allow_null=True)
    p25 = serializers.FloatField(allow_null=True)
    p75 = serializers.FloatField(allow_null=True)
    avg = serializers.FloatField(allow_null=True)
    sample_size = serializers.IntegerField()


class CubeCellSerializer(serializers.Serializer):
    """Cellule du cube multidimensionnel salaire (dimensions variables)."""

    country = serializers.CharField(required=False)
    skill = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    year = serializers.IntegerField(required=False)
    month = serializers.IntegerField(required=False)
    avg_salary = serializers.FloatField(allow_null=True)
    median_salary = serializers.FloatField(allow_null=True)
    job_count = serializers.IntegerField()


class DimensionSerializer(serializers.Serializer):
    """Valeurs disponibles d'une dimension (pour construire des requêtes)."""

    countries = serializers.ListField(child=serializers.CharField())
    skills = serializers.ListField(child=serializers.CharField())
    sources = serializers.ListField(child=serializers.CharField())
