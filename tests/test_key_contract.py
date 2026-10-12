# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Characterization of today's accounts key contract (X-API-ADMIN-KEY on ``customer/delete``).

Pins what the keyed route answers — quirks included — so moving the key check onto another key store cannot
change a status or a body. Keys come only from the ``make_api_key`` helper.
"""

import os
import secrets
from importlib.util import find_spec

import pytest
from django.contrib import admin
from django.core.management import call_command

from django_accounts.models import APIAdminKey, Customer
from django_accounts.utils.api_keys import ADMIN_KEY_HEADER, mask_key

LEGACY_ONLY = pytest.mark.skipif(
    not os.environ.get("ENTIRIUS_TEST_NO_ACCESS") and find_spec("django_access") is not None,
    reason="legacy path only",
)

ERASE_EMAIL = "testuser@example.com"


def _delete_url(channel_idx: str) -> str:
    return f"/api-admin/accounts/1/{channel_idx}/customer/delete"


def _delete(api_client, key: str | None, channel_idx: str = "test-channel"):
    headers = {} if key is None else {ADMIN_KEY_HEADER: key}
    return api_client.delete(_delete_url(channel_idx), {"email": ERASE_EMAIL}, format="json", **headers)


def _refusal(response) -> tuple[int, str, str]:
    """The v1 envelope puts the refusal text in ``data``, not in ``meta.message`` (quirk: positional arg)."""
    body = response.json()
    return response.status_code, body["meta"]["status"], body["data"]


@pytest.fixture(autouse=True)
def _live_key(channel, make_api_key):
    """Valid keys exist in every test, so a refusal proves the lookup, not an empty key store."""
    make_api_key(channel=channel)


@pytest.mark.django_db
class TestAdminKeyCustomerDelete:
    def test_unknown_channel_is_404_before_the_key(self, api_client, channel, make_api_key):
        response = _delete(api_client, make_api_key(channel=channel), channel_idx="no-such-channel")
        assert response.status_code == 404

    def test_missing_key_is_401(self, api_client, channel):
        assert _refusal(_delete(api_client, None)) == (401, "UNAUTHORIZED", "Invalid api admin key")

    def test_wrong_key_is_401(self, api_client, channel):
        assert _refusal(_delete(api_client, secrets.token_hex(32))) == (401, "UNAUTHORIZED", "Invalid api admin key")

    def test_other_channel_key_is_refused_like_a_wrong_key(self, api_client, channel, second_channel, make_api_key):
        wrong = _delete(api_client, secrets.token_hex(32))
        foreign_key = make_api_key(channel=second_channel)
        foreign = _delete(api_client, foreign_key)
        assert _refusal(foreign) == _refusal(wrong)
        assert foreign_key not in foreign.content.decode()

    def test_key_without_channel_is_refused(self, api_client, channel, make_api_key):
        assert _delete(api_client, make_api_key(channel=None)).status_code == 401

    def test_key_in_x_api_key_header_is_refused(self, api_client, channel, make_api_key):
        response = api_client.delete(
            _delete_url(channel.idx), {"email": ERASE_EMAIL}, format="json", HTTP_X_API_KEY=make_api_key(channel)
        )
        assert response.status_code == 401

    def test_right_key_deletes_the_customer(self, api_client, channel, customer, make_api_key):
        response = _delete(api_client, make_api_key(channel=channel))
        assert response.status_code == 200
        assert response.json()["data"] == {"deleted": True, "uid_ok": [str(customer.uid)]}
        assert not Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_public_token_validate_answers_without_a_key(api_client, channel):
    response = api_client.post(
        f"/api/accounts/1/{channel.idx}/customer/tokens/validate/", {"access": "not-a-token"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_valid"] is False


def test_mask_key_hides_short_keys_entirely():
    assert mask_key("abcd") == "…"
    assert mask_key("abcde") == "…bcde"


@pytest.mark.django_db
def test_admin_pages_never_show_the_raw_key(channel, admin_user, rf, settings):
    settings.ROOT_URLCONF = "tests.admin_urls"
    key = APIAdminKey.objects.create(channel=channel)
    model_admin = admin.site.get_model_admin(APIAdminKey)
    request = rf.get("/")
    request.user = admin_user
    for response in (model_admin.changelist_view(request), model_admin.change_view(request, str(key.pk))):
        html = response.render().content.decode()
        assert response.status_code == 200
        assert key.key not in html
        assert f"…{key.key[-4:]}" in html


@LEGACY_ONLY
@pytest.mark.django_db
class TestLegacyKeyPath:
    def test_command_creates_a_key(self, channel, tmp_path):
        path = tmp_path / "key"
        call_command("generate-api-admin-key", channel.idx, file_path=str(path))
        assert path.read_text() in APIAdminKey.objects.values_list("key", flat=True)

    def test_admin_allows_add_change_and_delete(self, channel, admin_user, rf):
        key = APIAdminKey.objects.create(channel=channel)
        model_admin = admin.site.get_model_admin(APIAdminKey)
        request = rf.get("/")
        request.user = admin_user
        assert model_admin.has_add_permission(request)
        assert model_admin.has_change_permission(request, key)
        assert model_admin.has_delete_permission(request, key)

    def test_admin_add_shows_only_the_masked_key(self, channel, admin_client_session, settings):
        settings.ROOT_URLCONF = "tests.admin_urls"
        response = admin_client_session.post(
            "/admin/django_accounts/apiadminkey/add/", {"channel": channel.pk}, follow=True
        )
        key = APIAdminKey.objects.latest("pk").key
        assert key not in response.content.decode()
        assert mask_key(key) in response.content.decode()
        listing = admin_client_session.get("/admin/django_accounts/apiadminkey/")
        assert key not in listing.content.decode()
