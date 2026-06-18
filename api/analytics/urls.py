from django.urls import path

from .views import (
    DimensionsView,
    SalaryCubeView,
    SalaryDailyView,
    SalaryStatsView,
)

urlpatterns = [
    path("salary-stats/", SalaryStatsView.as_view(), name="salary-stats"),
    path("salary-daily/", SalaryDailyView.as_view(), name="salary-daily"),
    path("salary-cube/", SalaryCubeView.as_view(), name="salary-cube"),
    path("dimensions/", DimensionsView.as_view(), name="dimensions"),
]
