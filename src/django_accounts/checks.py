# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Configuration checks (tag ``entirius_config``, shown by django-munin).

Warnings only: a service without the setting must still ``migrate``; the request answers a clean 500 instead.
"""

from django.core import checks

from django_accounts import settings

CODE = "accounts.redirect_urls"
URL_SHAPE = (
    "A storefront URL (string) the link appends ?key=... to, or a dict keyed by language iso2 whose values are "
    "URLs or dicts keyed by channel idx; 'default' is the fallback key at either level."
)


@checks.register("entirius_config", CODE)
def redirect_urls_configured(app_configs=None, **kwargs) -> list[checks.CheckMessage]:
    """The reset and signup mails are built from these URLs: without them the request fails with a 500."""
    messages = []
    if settings.RESET_PASSWORD_REDIRECT_URL is None:
        messages.append(
            checks.Warning(
                "RESET_PASSWORD_REDIRECT_URL is not set: customer/password/reset/ answers 500 and sends no mail.",
                hint=f"Set RESET_PASSWORD_REDIRECT_URL to the storefront's password reset page. {URL_SHAPE}",
                id="django_accounts.W001",
            )
        )
    if settings.EMAIL_DOUBLE_OPTIN and settings.NEW_ACCOUNT_REDIRECT_URL is None:
        messages.append(
            checks.Warning(
                "NEW_ACCOUNT_REDIRECT_URL is not set while EMAIL_DOUBLE_OPTIN is on: customer/signup/ answers 500.",
                hint=f"Set NEW_ACCOUNT_REDIRECT_URL to the storefront's account confirmation page. {URL_SHAPE}",
                id="django_accounts.W002",
            )
        )
    return messages
