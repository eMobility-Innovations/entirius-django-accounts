---
title: "Configuration"
description: "JWT settings, password policy, email configuration, and social login setup."
---

All settings are read from Django's `settings.py` via `getattr` with defaults. Override them in `settings_local.py`.

## Required: INSTALLED_APPS

```python
INSTALLED_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_accounts",
    # ... rest of apps
]
```

## Required: PRIVATE_DIR

`PRIVATE_DIR` is mandatory — the module raises `EnvironmentError` on startup if missing.

```python
PRIVATE_DIR = os.path.join(DATA_DIR, "private/")
```

Customer file attachments are stored at `{PRIVATE_DIR}/customer/`. Block this path from public web access in your web server config.

## Required: MIGRATION_0023_MECHANISM

Required for the wishlist-per-channel migration. Set before running migrations.

```python
# 1 — delete all existing wishlist data
# 2 — duplicate wishlists for every available channel
# 3 — assign each wishlist to the customer's source_channel
MIGRATION_0023_MECHANISM = 3
```

## JWT Settings

Configure via `SIMPLE_JWT` (from `djangorestframework-simplejwt`):

```python
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}
```

The module also reads these settings independently:

| Setting | Default | Description |
|---------|---------|-------------|
| `JWT_REFRESH_LIFETIME` | `3` | Refresh token lifetime (days) used by internal token logic |
| `JWT_SECRET` | **required** | Secret key for JWT signing; the module raises `OSError` on startup if missing |
| `JWT_ALGORITHM` | `"HS256"` | JWT signing algorithm |

## Required: Authentication Backend

The v1 customer views (`@authenticate`) call `django.contrib.auth.authenticate(request)`, which only
tries `AUTHENTICATION_BACKENDS`. Without `JWTAccessBackend` the Bearer token is never read and every
customer endpoint (`customer/me/`, profile, addresses, wishlist, password change, logout) is 401.

```python
AUTHENTICATION_BACKENDS = [
    "django_accounts.backends.JWTAccessBackend",
    "django.contrib.auth.backends.ModelBackend",  # required for /admin
]
```

Order is significant. JWT is checked first; Django's model backend is the fallback.

## Password Policy

All `ACCOUNTS_PASSWORD_*` settings are optional. Defaults are shown below.

| Setting | Default | Description |
|---------|---------|-------------|
| `ACCOUNTS_PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `ACCOUNTS_PASSWORD_MIN_CAPITAL_LETTERS` | `1` | Minimum uppercase letters |
| `ACCOUNTS_PASSWORD_MIN_SPECIAL_SYMBOLS` | `1` | Minimum special characters |
| `ACCOUNTS_PASSWORD_MIN_NUMBERS` | `1` | Minimum digits |
| `ACCOUNTS_PASSWORD_LIST_SYMBOLS` | `[~!@#$%^&*()_+{}":;'[]` | Recognized special characters |

To wire these into Django's validator chain:

```python
AUTH_PASSWORD_ACCOUNT_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": ACCOUNTS_PASSWORD_MIN_LENGTH},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "django_accounts.password_validators.CapitalSymbolAndNumbersValidator"},
    {"NAME": "django_accounts.password_validators.SpaceValidator"},
]
```

## Email Settings

Standard Django email settings apply. Example SMTP configuration:

```python
EMAIL_PORT = "587"
EMAIL_HOST = "smtp.example.com"
EMAIL_HOST_USER = "noreply@example.com"
EMAIL_HOST_PASSWORD = "smtp-password"
EMAIL_USE_TLS = True        # or EMAIL_USE_SSL = True — not both
DEFAULT_FROM_EMAIL = "noreply@example.com"
```

Module-specific email settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `EMAIL_DOUBLE_OPTIN` | `True` | Require email verification on registration |
| `ACCOUNTS_CUSTOMER_IS_ACTIVE_WITHOUT_DOUBLE_OPTIN` | `False` | Set customer `is_active=True` without email verification |

## Email Redirect URLs

Emails sent by the module (password reset, new account) contain links to the frontend. Configure the base URLs:

```python
RESET_PASSWORD_REDIRECT_URL = "https://example.com/pw-reset"
NEW_ACCOUNT_REDIRECT_URL = "https://example.com/"
```

Both settings accept a string or a dict for per-language or per-channel control:

```python
RESET_PASSWORD_REDIRECT_URL = {
    "pl": {
        "channel1": "https://example.com/pl/pw-reset",
        "channel2": "https://example.com/pl/pw-reset",
    },
    "en": {
        "channel1": "https://example.com/en/pw-reset",
    },
}
```

URL parameter key names (added to reset links):

| Setting | Default | Description |
|---------|---------|-------------|
| `NEW_ACCOUNT_REDIRECT_URL_PARAM_KEY` | `"key"` | Query param name for the verification key |
| `NEW_ACCOUNT_REDIRECT_URL_PARAM_UID` | `"uid"` | Query param name for user ID |
| `RESET_PASSWORD_REDIRECT_URL_PARAM_KEY` | `"key"` | Query param name for password reset key |
| `RESET_PASSWORD_EMAIL_LIFETIME` | `timedelta(days=7)` | Not read by the reset link (see below) |

A password reset link works once: setting the password, or a password change by any other route, ends it. So does
anything else Django's reset token is bound to: a change of the account's e-mail, or a login that records
`last_login` (the Django admin login does).
It expires after allauth's `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` or Django's `PASSWORD_RESET_TIMEOUT` (3 days
each by default), whichever comes first.

## Social Login (Google / Facebook)

### 1. Configure the OAuth provider

**Google:** Create credentials at [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Set the authorized redirect URI to:
```
https://yourdomain.com/api/accounts/v1/customer/login/google/callback/
```

**Facebook:** Create an app at [Facebook Developers](https://developers.facebook.com/apps/). Set the valid OAuth redirect URI to:
```
https://yourdomain.com/api/accounts/v1/customer/login/facebook/callback/
```

### 2. Register the provider in Django admin

Go to `Social Login → Providers` in the admin panel. Add a record with:

| Field | Value |
|-------|-------|
| Provider | `google` or `facebook` |
| Name | Display name |
| Client id | OAuth App ID |
| Key | OAuth App Secret |
| Callback url | The redirect URI from step 1 |
| is_enabled | checked |

### 3. Trigger login from the frontend

```
GET /api/accounts/v1/customer/login/google/
GET /api/accounts/v1/customer/login/facebook/
```

These return a redirect URL to the OAuth provider. After successful auth, the callback URL handles token creation.

## Address Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `NEW_ADDRESS_SHOULD_BE_DEFAULT` | `False` | Make a newly created address the default automatically |
| `BILLING_ADDRESS_EDITABLE` | `True` (unless `django_regon_api` installed) | Allow customers to edit billing address fields |
| `BILLING_ADDRESS_PHONE_EDITABLE` | `True` (unless `django_regon_api` installed) | Allow customers to edit phone on billing address |

## Access Control

| Setting | Default | Description |
|---------|---------|-------------|
| `IS_ACTIVE_REQUIRED` | `True` | Reject token refresh for inactive accounts |
| `IS_VERIFY_REQUIRED` | `False` | Reject token refresh for unverified emails |
| `ACCOUNTS_CHANNEL_BLACKLIST` | `{}` | Cross-channel access restrictions |

Channel blacklist example:

```python
# Users from channel1 cannot access channel2, but can access channel3.
# Users from channel2 cannot access channel1 or channel3.
ACCOUNTS_CHANNEL_BLACKLIST = {
    "channel1": ["channel2"],
    "channel2": ["channel1", "channel3"],
}
```

## Miscellaneous

| Setting | Default | Description |
|---------|---------|-------------|
| `T9N_DEFAULT_LANG` | `"pl"` | Default language for translatable fields |
| `SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API` | `None` | Whitelist of keys exposed from customer `extra` JSON in API responses |
| `WISHLIST_PRODUCT_PER_PAGE` | `30` | Pagination size for wishlist product listings |
| `ADMIN_DELETE_CUSTOMER_MAX_BATCH` | `5` | Max customers deletable in a single admin batch action |

## Magento Export Settings

Required only if using the `module-accounts-export-to-magento` command:

```python
MAGENTO2_URL_FOR_CHECKOUT_EXPORT = "https://magento.example.com"
MAGENTO2_TOKEN_FOR_CHECKOUT_EXPORT = "magento-api-token"
```

## Settings Reference

Three settings raise `OSError` at import time if unset: `JWT_SECRET`, `PRIVATE_DIR` and `MIGRATION_0023_MECHANISM`.

| Setting | Default | Description |
|---------|---------|-------------|
| `PRIVATE_DIR` | **required** | Root for private file storage |
| `MIGRATION_0023_MECHANISM` | **required** | Wishlist migration mode: 1=delete all, 2=multi-channel, 3=assign |
| `T9N_DEFAULT_LANG` | `"pl"` | Fallback language for name_t9n resolution |
| `EMAIL_DOUBLE_OPTIN` | `True` | Send confirmation email on signup |
| `ACCOUNTS_CUSTOMER_IS_ACTIVE_WITHOUT_DOUBLE_OPTIN` | `False` | Auto-activate when double optin off |
| `IS_ACTIVE_REQUIRED` | `True` | Block login if customer.is_active=False |
| `IS_VERIFY_REQUIRED` | `False` | Block login if customer.is_verified=False |
| `ACCOUNTS_PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `ACCOUNTS_PASSWORD_MIN_CAPITAL_LETTERS` | `1` | Capital letters required |
| `ACCOUNTS_PASSWORD_MIN_SPECIAL_SYMBOLS` | `1` | Special symbols required |
| `ACCOUNTS_PASSWORD_MIN_NUMBERS` | `1` | Numbers required |
| `JWT_REFRESH_LIFETIME` | `3` | Refresh token lifetime in days |
| `JWT_SECRET` | **required** | Secret for the short-lived social login token |
| `JWT_ALGORITHM` | `"HS256"` | JWT signing algorithm |
| `API_PUBLIC_BASE_URL` | `"api"` | Public URL prefix |
| `API_ADMIN_BASE_URL` | `"api-admin"` | Admin URL prefix |
| `NEW_ACCOUNT_REDIRECT_URL` | `None` | Email confirmation redirect URL |
| `RESET_PASSWORD_REDIRECT_URL` | `None` | Password reset redirect URL |
| `NEW_ADDRESS_SHOULD_BE_DEFAULT` | `False` | Auto-set new address as default |
| `BILLING_ADDRESS_EDITABLE` | auto | `False` if django_regon_api installed, else `True` |
| `BILLING_ADDRESS_PHONE_EDITABLE` | auto | `False` if django_regon_api installed, else `True` |
| `ADMIN_DELETE_CUSTOMER_MAX_BATCH` | `5` | Max customers per admin delete request |
| `WISHLIST_PRODUCT_PER_PAGE` | `30` | Wishlist pagination size |
| `ACCOUNTS_CHANNEL_BLACKLIST` | `{}` | `{channel_idx: [blacklisted_channel_idxs]}` applied on signup |
| `SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API` | `None` | Whitelist keys from customer.extra in profile API |
| `MAGENTO2_URL_FOR_CHECKOUT_EXPORT` | `None` | Magento2 export endpoint |
| `MAGENTO2_TOKEN_FOR_CHECKOUT_EXPORT` | `None` | Magento2 export API token |
