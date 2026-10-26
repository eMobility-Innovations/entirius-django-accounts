# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Password reset key (customer/password/reset/ and customer/password/reset/<key>/)."""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.test import Client

from django_accounts import settings as accounts_settings
from django_accounts.views.api import customer as customer_views

NEW_PASSWORD = "Reset-Test-2026!"


class _MailStub:
    """Stands in for ResetPasswordEmail (it needs a per-channel mail configuration) and keeps the link."""

    ExceptionType = customer_views.ResetPasswordEmail.ExceptionType
    links: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    def send(self, recipients, link):
        _MailStub.links.append(link)


@pytest.fixture
def reset_mail(monkeypatch):
    monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", "http://shop.test/reset-password")
    monkeypatch.setattr(customer_views, "ResetPasswordEmail", _MailStub)
    _MailStub.links = []
    return _MailStub


def _base(channel):
    return f"/{accounts_settings.PUBLIC_BASE_URL}/accounts/v1/{channel.idx}/customer/password/reset/"


def _request_key(channel, email, mail):
    resp = Client().post(_base(channel), data=json.dumps({"email": email}), content_type="application/json")
    assert resp.status_code == 200
    return parse_qs(urlparse(mail.links[-1]).query)[accounts_settings.RESET_PASSWORD_REDIRECT_URL_PARAM_KEY][0]


def _confirm(channel, key, password=NEW_PASSWORD):
    body = {"new_password": password, "new_password_check": password}
    return Client().post(f"{_base(channel)}{key}/", data=json.dumps(body), content_type="application/json")


@pytest.mark.django_db
class TestPasswordResetKey:
    def test_key_sets_the_password(self, customer, channel, reset_mail):
        key = _request_key(channel, customer.user.email, reset_mail)

        resp = _confirm(channel, key)

        assert resp.status_code == 200
        customer.user.refresh_from_db()
        assert customer.user.check_password(NEW_PASSWORD)

    def test_key_works_once(self, customer, channel, reset_mail):
        key = _request_key(channel, customer.user.email, reset_mail)
        assert _confirm(channel, key).status_code == 200

        resp = _confirm(channel, key, "Another-Reset-2026!")

        assert resp.status_code == 403
        assert resp.json()["meta"]["status"] == "invalid_key"
        customer.user.refresh_from_db()
        assert customer.user.check_password(NEW_PASSWORD)

    def test_key_stops_working_once_the_password_changes(self, customer, channel, reset_mail):
        key = _request_key(channel, customer.user.email, reset_mail)
        customer.user.set_password("Changed-Elsewhere-2026!")
        customer.user.save()

        resp = _confirm(channel, key)

        assert resp.status_code == 403
        assert resp.json()["meta"]["status"] == "invalid_key"

    def test_email_confirmation_key_is_not_a_reset_key(self, customer, channel):
        # allauth signs the e-mail address pk under its own salt for the signup confirmation link.
        key = EmailConfirmationHMAC(EmailAddress.objects.get(user=customer.user)).key

        resp = _confirm(channel, key)

        assert resp.status_code == 403
        assert resp.json()["meta"]["status"] == "invalid_key"
        customer.user.refresh_from_db()
        assert not customer.user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
class TestPasswordResetNotConfigured:
    def test_unset_redirect_url_answers_a_clean_500_without_mail(self, customer, channel, monkeypatch, caplog):
        monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", None)
        monkeypatch.setattr(customer_views, "ResetPasswordEmail", _MailStub)
        _MailStub.links = []

        resp = Client().post(
            _base(channel), data=json.dumps({"email": customer.user.email}), content_type="application/json"
        )

        assert resp.status_code == 500
        meta = resp.json()["meta"]
        assert meta["status"] == "NOT_CONFIGURED"
        assert meta["message"] == "Password reset is not available"
        assert "RESET_PASSWORD_REDIRECT_URL" not in resp.content.decode()
        assert _MailStub.links == []
        assert "RESET_PASSWORD_REDIRECT_URL is not set" in caplog.text
