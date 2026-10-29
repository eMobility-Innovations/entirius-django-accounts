# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
from datetime import timedelta

from django.conf import settings

DEBUG = getattr(settings, "DEBUG", False)

# API
PUBLIC_BASE_URL = getattr(settings, "API_PUBLIC_BASE_URL", "api").strip("/")
ADMIN_BASE_URL = getattr(settings, "API_ADMIN_BASE_URL", "api-admin").strip("/")
ACCOUNTS_NATIVE_AUTH_ENABLED = getattr(settings, "ACCOUNTS_NATIVE_AUTH_ENABLED", True)

# EMAIL SETTINGS
EMAIL_DOUBLE_OPTIN = getattr(settings, "EMAIL_DOUBLE_OPTIN", True)
ACCOUNTS_CUSTOMER_IS_ACTIVE_WITHOUT_DOUBLE_OPTIN = getattr(
    settings, "ACCOUNTS_CUSTOMER_IS_ACTIVE_WITHOUT_DOUBLE_OPTIN", False
)

SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API = getattr(settings, "SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API", None)
NEW_ADDRESS_SHOULD_BE_DEFAULT = getattr(settings, "NEW_ADDRESS_SHOULD_BE_DEFAULT", False)
RESET_PASSWORD_EMAIL_LIFETIME = getattr(settings, "RESET_PASSWORD_EMAIL_LIFETIME", timedelta(days=7))

ACCOUNTS_PASSWORD_MIN_LENGTH = getattr(settings, "ACCOUNTS_PASSWORD_MIN_LENGTH", 8)
ACCOUNTS_PASSWORD_MIN_CAPITAL_LETTERS = getattr(settings, "ACCOUNTS_PASSWORD_MIN_CAPITAL_LETTERS", 1)
ACCOUNTS_PASSWORD_MIN_SPECIAL_SYMBOLS = getattr(settings, "ACCOUNTS_PASSWORD_MIN_SPECIAL_SYMBOLS", 1)
ACCOUNTS_PASSWORD_MIN_NUMBERS = getattr(settings, "ACCOUNTS_PASSWORD_MIN_NUMBERS", 1)
ACCOUNTS_PASSWORD_LIST_SYMBOLS = getattr(settings, "ACCOUNTS_PASSWORD_LIST_SYMBOLS", "[~!@#$%^&*()_+{}\":;'[]")

# PASSWORD SETTINGS
ACCOUNT_VALIDATORS = [
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

AUTH_PASSWORD_ACCOUNT_VALIDATORS = getattr(settings, "AUTH_PASSWORD_ACCOUNT_VALIDATORS", ACCOUNT_VALIDATORS)

NEW_ACCOUNT_REDIRECT_URL = getattr(settings, "NEW_ACCOUNT_REDIRECT_URL", None)
NEW_ACCOUNT_REDIRECT_URL_PARAM_KEY = getattr(settings, "NEW_ACCOUNT_REDIRECT_URL_PARAM_KEY", "key")
NEW_ACCOUNT_REDIRECT_URL_PARAM_UID = getattr(settings, "NEW_ACCOUNT_REDIRECT_URL_PARAM_UID", "uid")
RESET_PASSWORD_REDIRECT_URL = getattr(settings, "RESET_PASSWORD_REDIRECT_URL", None)
RESET_PASSWORD_REDIRECT_URL_PARAM_KEY = getattr(settings, "RESET_PASSWORD_REDIRECT_URL_PARAM_KEY", "key")
CMS_RESET_PASSWORD_REDIRECT_URL = getattr(settings, "CMS_RESET_PASSWORD_REDIRECT_URL", None)

JWT_REFRESH_LIFETIME = getattr(settings, "JWT_REFRESH_LIFETIME", 3)
JWT_SECRET = getattr(settings, "JWT_SECRET", None)
if not JWT_SECRET:
    raise OSError("Setting JWT_SECRET is not set. Override in service settings.")
JWT_ALGORITHM = getattr(settings, "JWT_ALGORITHM", "HS256")

IS_ACTIVE_REQUIRED = getattr(settings, "IS_ACTIVE_REQUIRED", True)
IS_VERIFY_REQUIRED = getattr(settings, "IS_VERIFY_REQUIRED", False)

WISHLIST_PRODUCT_PER_PAGE = getattr(settings, "WISHLIST_PRODUCT_PER_PAGE", 30)


ADMIN_DELETE_CUSTOMER_MAX_BATCH = getattr(settings, "ADMIN_DELETE_CUSTOMER_MAX_BATCH", 5)

# CUSTOMER FILES
PRIVATE_DIR = getattr(settings, "PRIVATE_DIR", None)
if not PRIVATE_DIR:
    raise OSError("Setting PRIVATE_DIR is not set. Default should be '/private'.")
CUSTOMER_DIR = os.path.join(PRIVATE_DIR, "customer/")

if getattr(settings, "BILLING_ADDRESS_PHONE_EDITABLE", "") in [True, False]:
    BILLING_ADDRESS_PHONE_EDITABLE = settings.BILLING_ADDRESS_PHONE_EDITABLE
elif "django_regon_api" in settings.INSTALLED_APPS:
    BILLING_ADDRESS_PHONE_EDITABLE = False
else:
    BILLING_ADDRESS_PHONE_EDITABLE = True

if getattr(settings, "BILLING_ADDRESS_EDITABLE", "") in [True, False]:
    BILLING_ADDRESS_EDITABLE = settings.BILLING_ADDRESS_EDITABLE
elif "django_regon_api" in settings.INSTALLED_APPS:
    BILLING_ADDRESS_EDITABLE = False
else:
    BILLING_ADDRESS_EDITABLE = True

USE_I18N = True
USE_L10N = True
USE_TZ = True

MAGENTO2_URL_FOR_CHECKOUT_EXPORT = getattr(settings, "MAGENTO2_URL_FOR_CHECKOUT_EXPORT", None)
MAGENTO2_TOKEN_FOR_CHECKOUT_EXPORT = getattr(settings, "MAGENTO2_TOKEN_FOR_CHECKOUT_EXPORT", None)

# example: {"channel_idx": ["channel_idx_1", "channel_idx_2"]}
ACCOUNTS_CHANNEL_BLACKLIST = getattr(settings, "ACCOUNTS_CHANNEL_BLACKLIST", {})

T9N_DEFAULT_LANG = getattr(settings, "T9N_DEFAULT_LANG", "pl")

# 1 - delete all
# 2 - multiple records for each channel
# 3 - assign wishlist to customer channel
MIGRATION_0023_MECHANISM = getattr(settings, "MIGRATION_0023_MECHANISM", None)

if not MIGRATION_0023_MECHANISM:
    raise OSError("Setting MIGRATION_0023_MECHANISM is not set")
