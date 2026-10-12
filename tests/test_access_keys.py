# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The access path: with django_access installed the erase key is an access token (``verify_api_key``).

Legacy keys reach it only through the import (``make_api_key``); the legacy table is never read on this path.
No customer carries the erase email, so a key that passes answers 404 "Customer account not found" — distinct
from the 401 of a refused key and from the 404 of an unknown channel.
"""

import os
import re
import secrets
from datetime import timedelta
from unittest.mock import patch

import pytest

if os.environ.get("ENTIRIUS_TEST_NO_ACCESS"):
    pytest.skip("legacy path run", allow_module_level=True)
pytest.importorskip("django_access")

from django.contrib import admin  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.messages.storage.fallback import FallbackStorage  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.core.management import CommandError, call_command  # noqa: E402
from django.utils import timezone  # noqa: E402
from django_access.models import ApiToken, Application  # noqa: E402
from django_access.services.access_service import Actor  # noqa: E402
from django_access.services.tokens import hash_key, issue_token, revoke_token, set_token_expiry  # noqa: E402

from django_accounts.models import APIAdminKey, Customer  # noqa: E402
from django_accounts.utils.api_keys import ADMIN_KEY_HEADER, ERASE_SCOPE, key_is_valid, token_command  # noqa: E402

CHANNEL, SECOND = "test-channel", "second-channel"
API_KEY, ADMIN_KEY = "HTTP_X_API_KEY", ADMIN_KEY_HEADER
SYSTEM = Actor()


@pytest.fixture
def erase(api_client):
    def erase(key: str, channel_idx: str = CHANNEL, header: str = ADMIN_KEY):
        url = f"/api-admin/accounts/1/{channel_idx}/customer/delete"
        return api_client.delete(url, {"email": "nobody@example.com"}, format="json", **{header: key})

    return erase


_URL = f"/api-admin/accounts/1/{CHANNEL}/customer/delete"
_BODY = {"email": "nobody@example.com"}


def _passed(response) -> bool:
    return response.status_code == 404 and response.json()["meta"]["message"] == "Customer account not found"


def _refused(response) -> bool:
    return response.status_code == 401 and response.json()["data"] == "Invalid api admin key"


@pytest.fixture
def issue(db):
    """Issue a token of one scope; a secret scope gets the expiry it must carry."""
    application = Application.objects.create(name="accounts-tests")

    def issue(scope: str = ERASE_SCOPE, channel_idx: str | None = None) -> tuple[ApiToken, str]:
        expiry = timezone.now() + timedelta(days=30)
        return issue_token(application, scopes=[scope], channel_idx=channel_idx, expires_at=expiry, actor=SYSTEM)

    return issue


def _later(days: int):
    return patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=days))


@pytest.mark.django_db
class TestTokenLifecycle:
    def test_revoked_token_is_refused(self, channel, issue, erase):
        token, raw = issue(channel_idx=CHANNEL)
        assert _passed(erase(raw))
        revoke_token(token, actor=SYSTEM)
        assert _refused(erase(raw))

    def test_legacy_token_without_expiry_keeps_working(self, channel, make_api_key, erase):
        raw = make_api_key(channel=channel)
        token = ApiToken.objects.get(key_hash=hash_key(raw))
        assert (token.legacy, token.expires_at) == (True, None)
        assert _passed(erase(raw))
        with _later(days=3650):
            assert _passed(erase(raw))

    def test_legacy_token_past_its_team_expiry_is_refused(self, channel, make_api_key, erase):
        raw = make_api_key(channel=channel)
        token = ApiToken.objects.get(key_hash=hash_key(raw))
        set_token_expiry(token, expires_at=timezone.now() + timedelta(days=1), actor=SYSTEM)
        assert _passed(erase(raw))
        with _later(days=2):
            assert _refused(erase(raw))

    def test_key_only_in_the_legacy_table_is_refused(self, channel, erase):
        raw = secrets.token_hex(32)
        APIAdminKey.objects.create(channel=channel, key=raw)
        assert _refused(erase(raw))


@pytest.mark.django_db
class TestScopeAndChannel:
    def test_token_of_another_channel_is_refused(self, channel, second_channel, issue, erase):
        _, raw = issue(channel_idx=SECOND)
        assert _refused(erase(raw))

    def test_unpinned_token_works_on_any_channel(self, channel, second_channel, issue, erase):
        _, raw = issue()
        assert _passed(erase(raw, CHANNEL))
        assert _passed(erase(raw, SECOND))

    @pytest.mark.parametrize("scope", ["checkout.erase", "checkout.storefront"])
    def test_checkout_token_is_refused(self, scope, channel, issue, erase):
        _, raw = issue(scope, CHANNEL)
        assert _refused(erase(raw))

    def test_erase_token_in_x_api_key_is_refused(self, channel, issue, erase):
        _, raw = issue(channel_idx=CHANNEL)
        assert _refused(erase(raw, header=API_KEY))

    def test_garbage_admin_key_is_not_rescued_by_an_erase_token_in_x_api_key(self, channel, issue, api_client):
        _, raw = issue(channel_idx=CHANNEL)
        response = api_client.delete(_URL, _BODY, format="json", **{ADMIN_KEY: "garbage", API_KEY: raw})
        assert _refused(response)

    @pytest.mark.parametrize("x_api_key", ["storefront", "garbage"])
    def test_admin_key_wins_over_x_api_key(self, x_api_key, channel, issue, api_client):
        _, raw = issue(channel_idx=CHANNEL)
        _, storefront = issue("checkout.storefront", CHANNEL)
        other = storefront if x_api_key == "storefront" else "garbage"
        response = api_client.delete(_URL, _BODY, format="json", **{ADMIN_KEY: raw, API_KEY: other})
        assert _passed(response)

    def test_unknown_channel_is_404_before_the_key(self, channel, issue, erase):
        _, raw = issue()
        response = erase(raw, "no-such-channel")
        assert response.status_code == 404
        assert response.json()["data"] == "Channel does not exist"


@pytest.mark.django_db
def test_every_failure_gives_one_response(channel, second_channel, issue, erase, api_client):
    legacy_only = secrets.token_hex(32)
    APIAdminKey.objects.create(channel=channel, key=legacy_only)
    expired, expired_raw = issue(channel_idx=CHANNEL)
    ApiToken.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    revoked, revoked_raw = issue(channel_idx=CHANNEL)
    revoke_token(revoked, actor=SYSTEM)
    keys = {
        "unknown": "ent_api_" + secrets.token_urlsafe(32),
        "expired": expired_raw,
        "revoked": revoked_raw,
        "wrong scope": issue("checkout.erase", CHANNEL)[1],
        "wrong channel": issue(channel_idx=SECOND)[1],
        "legacy table only": legacy_only,
        "legacy format unknown": secrets.token_hex(32),
    }
    responses = {kind: erase(raw) for kind, raw in keys.items()}
    responses["missing header"] = api_client.delete(_URL, _BODY, format="json")
    outcomes = {kind: (response.status_code, response.content) for kind, response in responses.items()}
    assert len(set(outcomes.values())) == 1, outcomes
    assert outcomes["unknown"][0] == 401


@pytest.mark.django_db
def test_key_admin_is_read_only(channel, admin_user, rf, settings):
    settings.ROOT_URLCONF = "tests.admin_urls"
    key = APIAdminKey.objects.create(channel=channel)
    model_admin = admin.site.get_model_admin(APIAdminKey)
    request = rf.get("/")
    request.user = admin_user
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, key)
    assert not model_admin.has_delete_permission(request, key)


@pytest.mark.django_db
def test_key_admin_message_masks_the_key(channel, admin_user, rf, settings):
    """A Django message lives in a cookie: the full key must never reach it."""
    settings.ROOT_URLCONF = "tests.admin_urls"
    request = rf.post("/")
    request.user, request.session = admin_user, {}
    request._messages = FallbackStorage(request)
    key = APIAdminKey(channel=channel)
    admin.site.get_model_admin(APIAdminKey).save_model(request, key, form=None, change=False)
    (message,) = [str(m) for m in request._messages]
    assert key.key not in message
    assert key.key[-4:] in message


@pytest.mark.django_db
class TestKeyIsValid:
    def _request(self, rf, raw: str):
        return rf.get("/", **{ADMIN_KEY: raw})

    def test_success_attaches_the_token(self, channel, issue, rf):
        token, raw = issue(channel_idx=CHANNEL)
        request = self._request(rf, raw)
        assert key_is_valid(request, scope=ERASE_SCOPE, channel_idx=CHANNEL)
        assert request.access_token.pk == token.pk

    def test_refusal_attaches_nothing(self, channel, issue, rf):
        _, raw = issue("checkout.erase", CHANNEL)
        request = self._request(rf, raw)
        assert not key_is_valid(request, scope=ERASE_SCOPE, channel_idx=CHANNEL)
        assert not hasattr(request, "access_token")


@pytest.mark.django_db
def test_key_command_refuses_and_names_the_token_command(channel, tmp_path):
    path = tmp_path / "key"
    match = re.escape(token_command(ERASE_SCOPE, CHANNEL))
    with pytest.raises(CommandError, match=match):
        call_command("generate-api-admin-key", CHANNEL, file_path=str(path))
    assert not path.exists()
    assert not APIAdminKey.objects.exists()


# A pinned token erases only in its channel (D3); an unpinned one in every channel.

ERASED = "erased@example.com"


def _customer(channel, suffix: str) -> Customer:
    """One customer per channel can share an e-mail: the username differs, the e-mail is the same."""
    user = get_user_model().objects.create_user(username=f"{suffix}-{ERASED}", email=ERASED)
    return Customer.objects.create(user=user, source_channel=channel)


def _erase_email(api_client, raw: str, channel_idx: str = CHANNEL):
    url = f"/api-admin/accounts/1/{channel_idx}/customer/delete"
    return api_client.delete(url, {"email": ERASED}, format="json", **{ADMIN_KEY: raw})


def _kept(*customers: Customer) -> set[int]:
    return set(Customer.objects.filter(pk__in=[c.pk for c in customers]).values_list("pk", flat=True))


@pytest.mark.django_db
class TestPinnedErase:
    def test_pinned_token_erases_only_its_channel(self, channel, second_channel, issue, api_client):
        own, other = _customer(channel, "a"), _customer(second_channel, "b")
        response = _erase_email(api_client, issue(channel_idx=CHANNEL)[1])
        assert response.status_code == 200
        assert response.json()["data"]["uid_ok"] == [str(own.uid)]
        assert _kept(own, other) == {other.pk}

    def test_email_only_in_another_channel_is_not_found(self, channel, second_channel, issue, api_client):
        other = _customer(second_channel, "b")
        response = _erase_email(api_client, issue(channel_idx=CHANNEL)[1])
        assert _passed(response)
        assert _kept(other) == {other.pk}

    def test_not_found_matches_an_unknown_email(self, channel, second_channel, issue, api_client, erase):
        _customer(second_channel, "b")
        raw = issue(channel_idx=CHANNEL)[1]
        assert _erase_email(api_client, raw).content == erase(raw).content

    def test_customer_without_source_channel_is_kept(self, channel, issue, api_client):
        orphan = _customer(None, "x")
        assert _passed(_erase_email(api_client, issue(channel_idx=CHANNEL)[1]))
        assert _kept(orphan) == {orphan.pk}

    def test_unpinned_token_erases_every_channel(self, channel, second_channel, issue, api_client):
        own, other, orphan = _customer(channel, "a"), _customer(second_channel, "b"), _customer(None, "x")
        assert _erase_email(api_client, issue()[1]).status_code == 200
        assert _kept(own, other, orphan) == set()


# Staff login (customer/tokens/) behind access' failed-login guard — the route the CMS logs staff in through.

PASSWORD = "Test1234!"
_LOGIN_URL = f"/api/accounts/1/{CHANNEL}/customer/tokens/"


@pytest.fixture
def login(customer, api_client, settings):
    """Small limits (3 per user + address, 5 per address); the locmem cache starts empty."""
    settings.AUTH_TOKEN_MAX_FAILURES_PER_USER_IP = 3
    settings.AUTH_TOKEN_MAX_FAILURES_PER_IP = 5
    settings.AUTH_TOKEN_FAILURE_WINDOW_S = 600
    cache.clear()

    def login(password: str, email: str = "testuser@example.com", addr: str = "192.0.2.10"):
        body = {"email": email, "password": password}
        return api_client.post(_LOGIN_URL, body, format="json", REMOTE_ADDR=addr)

    return login


def _codes(login, n: int, **kwargs) -> list[int]:
    return [login("wrong", **kwargs).status_code for _ in range(n)]


@pytest.mark.django_db
class TestStaffLoginGuard:
    def test_wrong_passwords_block_the_user_on_that_address(self, login):
        assert _codes(login, 3) == [403] * 3
        response = login(PASSWORD)
        assert response.status_code == 429
        assert response["Retry-After"] == "600"
        assert response.json()["meta"]["message"] == "throttled"
        assert login(PASSWORD, addr="192.0.2.99").status_code == 200

    def test_another_user_follows_the_per_address_limit(self, login):
        assert _codes(login, 3, email="ghost@example.com") == [403] * 3
        assert _codes(login, 2, email="other@example.com") == [403] * 2
        assert login(PASSWORD).status_code == 429
        assert login(PASSWORD, addr="192.0.2.99").status_code == 200

    def test_success_clears_the_per_user_counter(self, login):
        assert _codes(login, 2) == [403] * 2
        assert login(PASSWORD).status_code == 200
        assert _codes(login, 2) == [403] * 2
        assert login(PASSWORD).status_code == 200

    def test_padded_email_hits_the_same_counter(self, login):
        assert _codes(login, 3, email=" testuser@example.com\t") == [403] * 3
        assert login(PASSWORD).status_code == 429

    def test_without_access_failures_are_never_counted(self, login):
        with patch("django_accounts.views.api.token.access_installed", return_value=False):
            assert _codes(login, 6) == [403] * 6
            assert login(PASSWORD).status_code == 200
