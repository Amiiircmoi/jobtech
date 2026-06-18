"""
Django settings for jobtech_api.

Configuration externalisée via variables d'environnement (django-environ) :
aucun secret n'est codé en dur. Voir `.env.example` à la racine du dépôt.
Cible de stockage unique : PostgreSQL (DATABASE_URL).
"""

from datetime import timedelta
from pathlib import Path

import environ

# api/jobtech_api/settings.py -> BASE_DIR = api/
BASE_DIR = Path(__file__).resolve().parent.parent
# Racine du dépôt (où vit le .env partagé par l'API, l'ETL et docker-compose)
REPO_ROOT = BASE_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
# Lit .env s'il existe (en prod : variables injectées par l'orchestrateur/conteneur)
environ.Env.read_env(REPO_ROOT / ".env")

# ── Sécurité ──────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# ── Applications ──────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "jobtech_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "jobtech_api.wsgi.application"

# ── Base de données : PostgreSQL unique (corrige le multi-SQLite + la typo) ─
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# ── Validation des mots de passe ──────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Django REST Framework : auth JWT, quotas, pagination, schéma OpenAPI ────
REST_FRAMEWORK = {
    # Authentification : JWT (Bearer) + session pour l'IHM navigable.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Par défaut : lecture seule pour tous, écriture réservée aux authentifiés.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # Quotas / throttling.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "1000/day",
    },
    # Pagination (réponses bornées).
    "DEFAULT_PAGINATION_CLASS": "analytics.pagination.CustomPagination",
    "PAGE_SIZE": 50,
    # Doc / schéma.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "jobtech API",
    "DESCRIPTION": "Indicateurs du marché de l'emploi Tech (salaires, volumes) "
    "servis depuis un Data Warehouse en étoile. Versionnée /api/v1/.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# JWT : durée de vie courte + refresh.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

# ── i18n ──────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Fichiers statiques ────────────────────────────────────────────────────
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Durcissement sécurité ─────────────────────────────────────────────────
# La redirection HTTPS est OPT-IN (uniquement derrière un vrai terminateur TLS,
# ex. VPS/reverse-proxy) : sinon CI, conteneurs HTTP et tests boucleraient en 301.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
