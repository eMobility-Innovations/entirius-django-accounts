# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Throttles of the public v1 function views (login, signup, password reset).

Scopes are overridable through ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``; the class-level ``rate`` is the
fallback when a scope is missing or malformed, so ``get_rate`` never returns ``None`` (DRF: no throttling).
Per-IP throttles use ``django_utils.api.client_ip`` (``settings.CLIENT_IP_HEADER``). Per-email throttles key on a
hash of the normalized address, never the address itself.
"""

import hashlib
import json
from functools import wraps

from django.http import JsonResponse
from django_utils.api.client_ip import ClientIPThrottleMixin
from django_utils.api.responses import Response, to_json_response
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


def throttled_response(request, wait: float | None, detail: str = "Request was throttled.") -> JsonResponse:
    """The 429 of the v1 views: status, ``Retry-After`` and DRF's detail, in this API's envelope."""
    request.customer = None  # nothing for save_ip_and_country to record
    response = to_json_response(Response({"detail": detail}, status="ERR", message="throttled", status_code=429))
    response["Retry-After"] = str(int(wait) if wait else 1)
    return response


def request_email(request) -> str | None:
    """The normalized ``email`` of a JSON body; None when absent or unreadable."""
    try:
        email = json.loads(request.body).get("email")
    except (ValueError, AttributeError):
        return None
    return email.strip().lower() if isinstance(email, str) and email.strip() else None


class _AccountsThrottle(SimpleRateThrottle):
    default_rate = "10/hour"  # class-level fallback; subclasses override

    def __init__(self) -> None:
        # DRF skips get_rate() when the class has ``rate``; the configured scope must win over the fallback.
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

    def get_rate(self) -> str:
        rate = (api_settings.DEFAULT_THROTTLE_RATES or {}).get(self.scope)
        if not isinstance(rate, str) or "/" not in rate:  # parse_rate accepts None: that would mean no throttling
            return self.default_rate
        try:
            self.parse_rate(rate)
        except (ValueError, KeyError, IndexError, AttributeError):  # missing or malformed: keep the fallback
            return self.default_rate
        return rate


class _IPThrottle(ClientIPThrottleMixin, _AccountsThrottle):
    def get_cache_key(self, request, view) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class _EmailThrottle(_AccountsThrottle):
    def get_cache_key(self, request, view) -> str | None:
        email = request_email(request)
        if email is None:
            return None
        digest = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class LoginIPThrottle(_IPThrottle):
    scope = "accounts_login_ip"
    default_rate = "30/min"


class SignupIPThrottle(_IPThrottle):
    scope = "accounts_signup_ip"
    default_rate = "10/hour"


class SignupEmailThrottle(_EmailThrottle):
    scope = "accounts_signup_email"
    default_rate = "3/hour"


class PasswordResetIPThrottle(_IPThrottle):
    scope = "accounts_password_reset_ip"
    default_rate = "10/hour"


class PasswordResetEmailThrottle(_EmailThrottle):
    scope = "accounts_password_reset_email"
    default_rate = "3/hour"


def throttle(*throttle_classes):
    """Function-view decorator: the first throttle that refuses answers 429. Put it above ``save_ip_and_country``."""

    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            for throttle_class in throttle_classes:
                limiter = throttle_class()
                if not limiter.allow_request(request, view):
                    return throttled_response(request, limiter.wait())
            return view(request, *args, **kwargs)

        return _wrapped

    return decorator
