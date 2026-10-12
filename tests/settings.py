# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
from importlib.util import find_spec

import dj_database_url

# PATHS
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "."))

# SECURITY
SECRET_KEY = "not-so-secret-test-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Required by django_accounts.settings (raises EnvironmentError if missing)
PRIVATE_DIR = os.path.join(DATA_DIR, "tmp/private-test/")
MIGRATION_0023_MECHANISM = 1

# API URL prefixes
API_PUBLIC_BASE_URL = "api"
API_ADMIN_BASE_URL = "api-admin"

# JWT (required by django_accounts.settings — no hardcoded default)
JWT_SECRET = "test-jwt-secret-not-for-production"

# T9N
T9N_DEFAULT_LANG = "en"

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_regional",
    "django_email",
    "django_captcha",
    "django_accounts",
    "drf_spectacular",
]
# Soft dependency: with django-access importable (zeno) keys are checked as access tokens.
if find_spec("django_access") and not os.environ.get("ENTIRIUS_TEST_NO_ACCESS"):
    INSTALLED_APPS.append("django_access")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database: postgres via DATABASE_URL (CI provides a postgres service; locally point it
# at any postgres 15+ — the default matches the CI service).
DATABASES = {
    "default": dj_database_url.config(default="postgresql://postgres:postgres@localhost:5432/test"),
}

# Auth
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static
STATIC_URL = "/static/"

# Django 3.2+
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# allauth
SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = "none"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# URL conf
ROOT_URLCONF = "django_accounts.urls"
