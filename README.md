# entirius-django-accounts

A Django module for customer accounts in Entirius, the open-source modular ecommerce platform: registration, JWT login, address book and wishlist.
It serves a channel-scoped public API for the storefront and a read-only admin API for the CMS.

[![PyPI](https://img.shields.io/pypi/v/entirius-django-accounts.svg)](https://pypi.org/project/entirius-django-accounts/)
[![Python](https://img.shields.io/pypi/pyversions/entirius-django-accounts.svg)](https://pypi.org/project/entirius-django-accounts/)
[![License: MPL-2.0](https://img.shields.io/badge/license-MPL--2.0-blue.svg)](https://github.com/entirius/entirius-django-accounts/blob/develop/LICENSE)

## What it does

- Registers customers with double opt-in email confirmation and a configurable password policy.
- Logs customers in with JWT access and refresh tokens, including logout and password reset.
- Keeps an address book with billing and shipping defaults and file attachments in private storage.
- Stores one wishlist per customer and sales channel, and merges a guest wishlist on login.
- Supports social login with Google and Facebook.
- Imports accounts and addresses from CSV, and deletes a customer on request through an admin endpoint.

## Installation

```shell
uv add entirius-django-accounts
pip install entirius-django-accounts
```

Extras: `entirius-django-accounts[pim]` adds the product-representation sync from `entirius-django-pim`.

```python
INSTALLED_APPS = [
    ...
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_regional",
    "django_utils",
    "django_email",
    "django_accounts",
]

# urls.py
urlpatterns = [
    path("", include("django_accounts.urls")),
]

JWT_SECRET = "<random secret>"
PRIVATE_DIR = "/private"            # root of private file storage
MIGRATION_0023_MECHANISM = 1        # wishlist restructuring mode; 1 on a fresh installation
```

`JWT_SECRET`, `PRIVATE_DIR` and `MIGRATION_0023_MECHANISM` are read at import time and the module refuses to start
without them. Settings reference: https://github.com/entirius/entirius-django-accounts/blob/develop/docs/configuration.md

The customer-delete admin endpoint takes a key. Where `entirius-django-access` is installed (the backend service
installs it when available) the key is an access token:

```shell
python manage.py access_token create --application <name> --create-application --scope accounts.erase --channel <idx>
```

Only without `django_access` the key comes from the module's own command:

```shell
python manage.py generate-api-admin-key <channel_idx>
```

## Quick start

```python
from django_accounts.services.admin_service import list_customers

verified = list_customers(search="example.com", is_verified=True, ordering="-created_at")
```

## Requirements

- Python 3.11 or newer, Django 4.0 or newer.
- PostgreSQL (the test suite runs on it through `DATABASE_URL`).
- `django-allauth`, Django REST Framework, `djangorestframework-simplejwt`, `marshmallow`, `pydantic`, `drf-spectacular`.
- Entirius packages pulled in: `entirius-django-email`, `entirius-django-regional`, `entirius-django-utils`,
  `entirius-py-process-logger`, `entirius-py-idx-normalizator`, `entirius-py-int-enum-choices`.
- Optional: `entirius-django-pim` (the `pim` extra), `entirius-django-access` (keys as access tokens).

## Documentation

- Module docs: https://github.com/entirius/entirius-django-accounts/tree/develop/docs
- Entirius documentation: https://docs.entirius.com/
- Changelog: https://github.com/entirius/entirius-django-accounts/blob/develop/CHANGELOG.md

## Part of Entirius

This module runs inside the Entirius backend service (Volkanos) and owns customer identity for the storefront.

- Backend service: https://github.com/entirius/entirius-service-volkanos
- Docker harness: https://github.com/entirius/entirius-zeno
- Sibling modules: https://github.com/entirius/entirius-django-email, https://github.com/entirius/entirius-django-regional, https://github.com/entirius/entirius-django-access

## Development

```shell
make install     # sync dependencies (uv)
make check       # lint + format check (ruff)
make test        # test suite (pytest + pytest-django, needs PostgreSQL via DATABASE_URL)
```

Development and agent instructions: https://github.com/entirius/entirius-django-accounts/blob/develop/AGENTS.md

## License

Mozilla Public License 2.0 (MPL-2.0) — see https://github.com/entirius/entirius-django-accounts/blob/develop/LICENSE.
