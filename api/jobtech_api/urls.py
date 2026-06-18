"""Routage racine de l'API jobtech.

Versioning par URL : tous les endpoints métier sont sous /api/v1/.
Authentification JWT : /api/v1/auth/token/ + refresh.
Documentation OpenAPI/Swagger : /api/schema/ + /api/docs/.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    # Mini-dashboard de démo (consomme l'API v1)
    path("", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
    path("admin/", admin.site.urls),
    # ── Authentification JWT ──
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # ── Endpoints métier v1 ──
    path("api/v1/", include("analytics.urls")),
    # ── Schéma + documentation OpenAPI ──
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
