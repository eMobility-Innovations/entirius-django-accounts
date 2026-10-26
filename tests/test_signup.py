# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Signup (customer/signup/) response contract."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from django_accounts import settings as accounts_settings
from django_accounts.views.api import customer as customer_views

User = get_user_model()

PASSWORD = "Signup-Test-2026!"


class _MailStub:
    """Stands in for NewAccountEmail: the real one needs a per-channel mail configuration."""

    ExceptionType = customer_views.NewAccountEmail.ExceptionType

    def __init__(self, *args, **kwargs):
        pass

    def send(self, *args, **kwargs):
        pass


def _signup(channel, email):
    # Not reverse("signup"): the name is shared with the social-login routes and resolves to customer/tokenize/.
    url = f"/{accounts_settings.PUBLIC_BASE_URL}/accounts/v1/{channel.idx}/customer/signup/"
    body = {"email": email, "password": PASSWORD, "language": "en"}
    return Client().post(url, data=json.dumps(body), content_type="application/json")


@pytest.mark.django_db
class TestSignupResponse:
    def test_double_optin_response_has_no_password(self, channel, monkeypatch):
        monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", True)
        monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", "http://shop.test/user-handler")
        monkeypatch.setattr(customer_views, "NewAccountEmail", _MailStub)

        resp = _signup(channel, "optin@example.com")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "password" not in data
        assert data["email"] == "optin@example.com"
        assert data["uid"]
        assert User.objects.get(email="optin@example.com").check_password(PASSWORD)

    def test_without_double_optin_response_has_no_password(self, channel, monkeypatch):
        monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", False)

        resp = _signup(channel, "direct@example.com")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "password" not in data
        assert data["uid"]
        assert User.objects.get(email="direct@example.com").check_password(PASSWORD)

    def test_double_optin_without_redirect_url_answers_a_clean_500(self, channel, monkeypatch, caplog):
        monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", True)
        monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", None)
        sent = []
        monkeypatch.setattr(customer_views, "NewAccountEmail", type("Stub", (_MailStub,), {"send": sent.append}))

        resp = _signup(channel, "unconfigured@example.com")

        assert resp.status_code == 500
        meta = resp.json()["meta"]
        assert meta["status"] == "NOT_CONFIGURED"
        assert meta["message"] == "Account registration is not available"
        assert "NEW_ACCOUNT_REDIRECT_URL" not in resp.content.decode()
        assert sent == []
        assert not User.objects.filter(email="unconfigured@example.com").exists()
        assert "NEW_ACCOUNT_REDIRECT_URL is not set" in caplog.text
