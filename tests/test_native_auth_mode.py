# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""SSO-only deployments disable credentials, not their bearer sessions."""

import json

import pytest
from django.core import checks
from django.test import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from django_accounts import settings as accounts_settings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "endpoint",
    [
        "customer/tokens/",
        "customer/signup/",
        "customer/signup/unused-uid/",
        "customer/password/reset/",
        "customer/password/reset/unused-key/",
        "customer/password/change/",
    ],
)
def test_disabled_native_flows_refuse_before_processing(client, channel, monkeypatch, endpoint):
    monkeypatch.setattr(accounts_settings, "ACCOUNTS_NATIVE_AUTH_ENABLED", False, raising=False)

    response = client.post(f"/api/accounts/v1/{channel.idx}/{endpoint}", data="{}", content_type="application/json")

    assert response.status_code == 403
    assert response.json()["meta"]["status"] == "native_auth_disabled"


def test_native_auth_is_enabled_by_default(client, channel, customer):
    assert accounts_settings.ACCOUNTS_NATIVE_AUTH_ENABLED is True
    response = client.post(
        f"/api/accounts/v1/{channel.idx}/customer/tokens/",
        data=json.dumps({"email": customer.user.email, "password": "Test1234!"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["data"]["access"]


def test_disabled_native_auth_keeps_refresh_and_validation(client, channel, customer, monkeypatch):
    monkeypatch.setattr(accounts_settings, "ACCOUNTS_NATIVE_AUTH_ENABLED", False, raising=False)
    refresh = RefreshToken.for_user(customer.user)
    response = client.post(
        f"/api/accounts/v1/{channel.idx}/customer/tokens/refresh/",
        data=json.dumps({"refresh": str(refresh)}),
        content_type="application/json",
    )
    assert response.status_code == 200
    access = response.json()["data"]["access"]
    verified = client.post(
        f"/api/accounts/v1/{channel.idx}/customer/tokens/validate/",
        data=json.dumps({"access": access}),
        content_type="application/json",
    )
    assert verified.status_code == 200
    assert verified.json()["data"]["is_valid"] is True


@override_settings(
    AUTHENTICATION_BACKENDS=[
        "django_accounts.backends.JWTAccessBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]
)
def test_disabled_native_auth_keeps_bearer_profile_and_logout(client, channel, customer, monkeypatch):
    monkeypatch.setattr(accounts_settings, "ACCOUNTS_NATIVE_AUTH_ENABLED", False, raising=False)
    refresh = RefreshToken.for_user(customer.user)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}
    me = client.get(f"/api/accounts/v1/{channel.idx}/customer/me/", **headers)
    profile = client.get(f"/api/accounts/v1/{channel.idx}/customer/{customer.uid}/profile/", **headers)
    logout = client.post(
        f"/api/accounts/v1/{channel.idx}/customer/tokens/blacklist/",
        data=json.dumps({"refresh": str(refresh)}),
        content_type="application/json",
        **headers,
    )
    assert me.status_code == 200
    assert profile.status_code == 200
    assert logout.status_code == 200
    assert logout.json()["meta"]["status"] == "BLACKLISTED"


@pytest.mark.parametrize("enabled,expected", [(False, []), (True, ["django_accounts.W001", "django_accounts.W002"])])
def test_redirect_checks_only_require_urls_for_enabled_flows(monkeypatch, enabled, expected):
    monkeypatch.setattr(accounts_settings, "ACCOUNTS_NATIVE_AUTH_ENABLED", enabled, raising=False)
    monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", None)
    monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", None)
    monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", True)
    messages = checks.run_checks(tags=["accounts.redirect_urls"])
    assert [message.id for message in messages] == expected
