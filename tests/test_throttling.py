# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Throttles of login, signup and password reset (per IP, per email, header-based IP)."""

import json

import pytest
from django.core.cache import cache
from django.test import Client

from django_accounts import settings as accounts_settings
from django_accounts.utils.throttling import PasswordResetEmailThrottle, request_email

_ROUTES = {
    "login": "customer/tokens/",
    "signup": "customer/signup/",
    "reset": "customer/password/reset/",
}


@pytest.fixture
def rates(settings):
    def _set(**rates):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}

    return _set


def _post(channel, route, email, ip="10.0.0.1", **extra):
    url = f"/{accounts_settings.PUBLIC_BASE_URL}/accounts/v1/{channel.idx}/{_ROUTES[route]}"
    body = {"email": email, "password": "x", "language": "en"}
    return Client().post(url, data=json.dumps(body), content_type="application/json", REMOTE_ADDR=ip, **extra)


@pytest.mark.django_db
class TestPerIP:
    @pytest.mark.parametrize(
        ("route", "scope"),
        [("login", "accounts_login_ip"), ("signup", "accounts_signup_ip"), ("reset", "accounts_password_reset_ip")],
    )
    def test_ip_is_blocked_after_the_limit(self, channel, rates, route, scope):
        rates(**{scope: "2/hour"})

        statuses = [_post(channel, route, f"u{i}@example.com").status_code for i in range(3)]
        other_ip = _post(channel, route, "u9@example.com", ip="10.0.0.2").status_code

        assert 429 not in statuses[:2]
        assert statuses[2] == 429
        assert other_ip != 429

    def test_429_uses_the_api_envelope(self, channel, rates):
        rates(accounts_login_ip="1/hour")
        _post(channel, "login", "a@example.com")

        resp = _post(channel, "login", "a@example.com")

        assert resp.status_code == 429
        assert resp["Retry-After"].isdigit()
        assert resp.json()["meta"]["message"] == "throttled"

    def test_header_ip_is_used_when_configured(self, channel, rates, settings):
        settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
        rates(accounts_signup_ip="1/hour")

        first = _post(channel, "signup", "a@example.com", HTTP_CF_CONNECTING_IP="1.1.1.1")
        same_client = _post(channel, "signup", "b@example.com", ip="10.0.0.2", HTTP_CF_CONNECTING_IP="1.1.1.1")
        other_client = _post(channel, "signup", "c@example.com", HTTP_CF_CONNECTING_IP="2.2.2.2")

        assert first.status_code != 429
        assert same_client.status_code == 429
        assert other_client.status_code != 429


@pytest.mark.django_db
class TestPerEmail:
    @pytest.mark.parametrize(
        ("route", "scope"),
        [("signup", "accounts_signup_email"), ("reset", "accounts_password_reset_email")],
    )
    def test_email_is_blocked_across_ips_and_case(self, channel, rates, route, scope):
        rates(**{scope: "2/hour"})

        statuses = [
            _post(channel, route, email, ip=f"10.0.0.{i}").status_code
            for i, email in enumerate(["Same@Example.com", "same@example.com", " SAME@example.com "])
        ]
        other_email = _post(channel, route, "other@example.com", ip="10.0.0.9").status_code

        assert statuses[2] == 429
        assert 429 not in statuses[:2]
        assert other_email != 429

    def test_cache_key_has_no_raw_email(self, channel, rates):
        rates(accounts_password_reset_email="5/hour")
        _post(channel, "reset", "secret.person@example.com")

        keys = [key for key in cache._cache if "password_reset_email" in str(key)]

        assert len(keys) == 1
        assert "secret" not in keys[0] and "example" not in keys[0]

    def test_request_without_email_is_not_counted(self):
        class _Request:
            body = b"not json"

        assert request_email(_Request()) is None
        assert PasswordResetEmailThrottle().get_cache_key(_Request(), None) is None


class TestRateFallback:
    @pytest.mark.parametrize("bad", [None, "", "banana", "5/", "x/hour", 5])
    def test_malformed_rate_falls_back_to_the_class_rate(self, rates, bad):
        rates(accounts_password_reset_email=bad)

        assert PasswordResetEmailThrottle().rate == "3/hour"
        assert PasswordResetEmailThrottle().num_requests == 3

    def test_configured_rate_wins(self, rates):
        rates(accounts_password_reset_email="7/min")

        assert PasswordResetEmailThrottle().num_requests == 7
