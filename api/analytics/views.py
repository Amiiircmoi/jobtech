"""Endpoints analytiques servis depuis le Data Warehouse en étoile (PostgreSQL).

- /salary-stats/  : médiane, quartiles, moyenne (filtrable)
- /salary-daily/  : série temporelle de salaire moyen (filtrable)
- /salary-cube/   : cube multidimensionnel paramétrable
- /dimensions/    : valeurs disponibles des dimensions (découvrabilité)
"""

from django.db.models import Aggregate, Avg, Count, F, FloatField, Sum
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CountryDim, FactJob, SkillDim, SourceDim
from .serializers import (
    CubeCellSerializer,
    DimensionSerializer,
    SalaryDailySerializer,
    SalaryStatsSerializer,
)


class PercentileCont(Aggregate):
    """Agrégat ordonné PostgreSQL : percentile_cont(p) WITHIN GROUP (ORDER BY expr).

    Django ne fournit pas cet agrégat (l'ancien import contrib.postgres était erroné).
    """

    function = "PERCENTILE_CONT"
    name = "PercentileCont"
    output_field = FloatField()
    template = "%(function)s(%(percentile)s) WITHIN GROUP (ORDER BY %(expressions)s)"

    def __init__(self, expression, percentile, **extra):
        super().__init__(expression, percentile=percentile, **extra)


# Dimensions exposées : nom public → champ ORM
CUBE_DIMENSIONS = {
    "country": "country__iso2",
    "skill": "skill__tech_label",
    "source": "source__source_name",
    "year": "date_key__year",
    "month": "date_key__month",
}

_COMMON_FILTERS = [
    OpenApiParameter("country", OpenApiTypes.STR, description="Code pays ISO2 (ex. FR)"),
    OpenApiParameter("skill", OpenApiTypes.STR, description="Compétence normalisée (ex. python)"),
    OpenApiParameter("source", OpenApiTypes.STR, description="Source (ex. adzuna)"),
]


def _apply_filters(qs, params):
    """Filtres communs country / skill / source sur la table de faits."""
    if (country := params.get("country")):
        qs = qs.filter(country__iso2=country.upper())
    if (skill := params.get("skill")):
        qs = qs.filter(skill__tech_label=skill.lower())
    if (source := params.get("source")):
        qs = qs.filter(source__source_name=source.lower())
    return qs


@extend_schema(parameters=_COMMON_FILTERS, responses=SalaryStatsSerializer)
class SalaryStatsView(APIView):
    """Distribution salariale (médiane, P25, P75, moyenne) sur un périmètre filtré."""

    def get(self, request):
        qs = _apply_filters(FactJob.objects.all(), request.query_params)
        stats = qs.aggregate(
            median=PercentileCont("avg_salary", 0.5),
            p25=PercentileCont("avg_salary", 0.25),
            p75=PercentileCont("avg_salary", 0.75),
            avg=Avg("avg_salary"),
            sample_size=Count("id_fact"),
        )
        return Response(SalaryStatsSerializer(stats).data)


def _round(v):
    return round(v, 2) if v is not None else None


@extend_schema(parameters=_COMMON_FILTERS, responses=SalaryDailySerializer(many=True))
class SalaryDailyView(generics.ListAPIView):
    """Série temporelle du salaire moyen par jour (filtrable)."""

    serializer_class = SalaryDailySerializer

    def get_queryset(self):
        qs = _apply_filters(FactJob.objects.all(), self.request.query_params)
        # Alias internes (a/c) pour éviter la collision alias↔champ du modèle.
        agg = (
            qs.values("date_key")
            .annotate(a=Avg("avg_salary"), c=Sum("job_count"))
            .order_by("date_key")
        )
        return [
            {"date": r["date_key"], "avg_salary": _round(r["a"]), "job_count": r["c"]}
            for r in agg
        ]


@extend_schema(
    parameters=[
        *_COMMON_FILTERS,
        OpenApiParameter(
            "dimensions",
            OpenApiTypes.STR,
            description="Dimensions du cube séparées par des virgules "
            f"(parmi {', '.join(CUBE_DIMENSIONS)}). Défaut: country,skill",
        ),
    ],
    responses=CubeCellSerializer(many=True),
)
class SalaryCubeView(generics.ListAPIView):
    """Cube multidimensionnel : agrège salaire (moyenne, médiane) et volume selon
    les dimensions demandées (pays × compétence × source × année × mois)."""

    serializer_class = CubeCellSerializer

    def get_queryset(self):
        params = self.request.query_params
        requested = [d.strip() for d in params.get("dimensions", "country,skill").split(",")]
        dims = [d for d in requested if d in CUBE_DIMENSIONS] or ["country", "skill"]
        # Alias internes préfixés (d_*/m_*) pour éviter toute collision alias↔champ.
        value_fields = {f"d_{d}": F(CUBE_DIMENSIONS[d]) for d in dims}
        qs = _apply_filters(FactJob.objects.all(), params)
        agg = (
            qs.values(**value_fields)
            .annotate(
                m_avg=Avg("avg_salary"),
                m_median=PercentileCont("avg_salary", 0.5),
                m_count=Sum("job_count"),
            )
            .order_by(*[f"d_{d}" for d in dims])
        )
        return [
            {
                **{d: r[f"d_{d}"] for d in dims},
                "avg_salary": _round(r["m_avg"]),
                "median_salary": _round(r["m_median"]),
                "job_count": r["m_count"],
            }
            for r in agg
        ]


@extend_schema(responses=DimensionSerializer)
class DimensionsView(APIView):
    """Liste les valeurs disponibles des dimensions (pour construire des requêtes)."""

    def get(self, request):
        return Response(
            {
                "countries": list(CountryDim.objects.values_list("iso2", flat=True).order_by("iso2")),
                "skills": list(SkillDim.objects.values_list("tech_label", flat=True).order_by("tech_label")),
                "sources": list(SourceDim.objects.values_list("source_name", flat=True).order_by("source_name")),
            }
        )
