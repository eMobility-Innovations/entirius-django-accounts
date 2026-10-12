# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The one key check of the erase route (X-API-ADMIN-KEY).

With ``django_access`` installed a key is an access token checked by ``verify_api_key`` (scope + channel pin); the
legacy table is never read on that path — legacy keys live on as imported tokens (D28). Without the module: today's
legacy query, unchanged.
"""

from types import SimpleNamespace

from django.apps import apps

from django_accounts.models import APIAdminKey, Channel

ERASE_SCOPE = "accounts.erase"
ADMIN_KEY_HEADER = "HTTP_X_API_ADMIN_KEY"


def access_installed() -> bool:
    return apps.is_installed("django_access")


def mask_key(key: str) -> str:
    """What an admin page shows of a key: its last four characters."""
    return "…" if len(key) <= 4 else f"…{key[-4:]}"


def token_command(scope: str, channel_idx: str) -> str:
    """What replaces the legacy key command when access is installed."""
    return (
        f"manage.py access_token create --scope {scope} --channel {channel_idx} --expires-days <n> --application <name>"
    )


def key_is_valid(request, *, scope: str, channel_idx: str | None) -> bool:
    """True when X-API-ADMIN-KEY carries a key for ``scope`` on ``channel_idx``."""
    key = request.META.get(ADMIN_KEY_HEADER)
    if not key:
        return False
    if access_installed():
        return _token_is_valid(request, key, scope, channel_idx)
    return APIAdminKey.objects.filter(key=key, channel=request.channel).exists()


def _token_is_valid(request, key: str, scope: str, channel_idx: str | None) -> bool:
    """``verify_api_key`` sees only X-API-ADMIN-KEY: an X-API-KEY header never stands in for it."""
    from django_access.services.tokens import verify_api_key

    token = verify_api_key(SimpleNamespace(META={ADMIN_KEY_HEADER: key}), scope, channel_idx)
    if token is not None:
        request.access_token = token
    return token is not None


def erase_channel(request) -> Channel | None:
    """The channel a GDPR erase is limited to: the URL's when the access token is pinned, else None (every channel).

    The key check already refused a pin that differs from the URL, so the request's channel is the pin.
    """
    token = getattr(request, "access_token", None)
    return request.channel if token is not None and token.channel_idx else None
