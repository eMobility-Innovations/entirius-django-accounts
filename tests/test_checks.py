# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Configuration checks for the redirect URLs of the reset and signup mails."""

from django.core import checks

from django_accounts import settings as accounts_settings


def _accounts_ids() -> list[str]:
    return [m.id for m in checks.run_checks() if (m.id or "").startswith("django_accounts.")]


def test_unset_reset_url_warns(monkeypatch):
    monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", None)
    monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", "http://shop.test/user-handler")

    assert _accounts_ids() == ["django_accounts.W001"]


def test_unset_signup_url_warns_only_with_double_optin(monkeypatch):
    monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", "http://shop.test/reset-password")
    monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", None)

    monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", True)
    assert _accounts_ids() == ["django_accounts.W002"]

    monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", False)
    assert _accounts_ids() == []


def test_set_urls_pass(monkeypatch):
    monkeypatch.setattr(accounts_settings, "RESET_PASSWORD_REDIRECT_URL", {"default": "http://shop.test/reset"})
    monkeypatch.setattr(accounts_settings, "NEW_ACCOUNT_REDIRECT_URL", "http://shop.test/user-handler")
    monkeypatch.setattr(accounts_settings, "EMAIL_DOUBLE_OPTIN", True)

    assert _accounts_ids() == []
