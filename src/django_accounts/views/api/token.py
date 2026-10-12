# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_utils.api.decorators import (
    api_view,
    authenticate,
    require_authentication,
    require_http_method,
    save_ip_and_country,
)
from django_utils.api.exceptions import Forbidden
from django_utils.api.responses import Response, to_json_response
from rest_framework.exceptions import AuthenticationFailed, Throttled
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from django_accounts import settings
from django_accounts.utils.api_keys import access_installed
from django_accounts.utils.decorators import channel_view

logger = logging.getLogger(__name__)


def check_if_active(customer):
    if settings.IS_ACTIVE_REQUIRED:
        if not customer.is_active:
            w = "User is not active."
            logger.debug(w)
            raise Forbidden(message=w, status="user_not_active")


def check_if_verified(customer):
    if settings.IS_VERIFY_REQUIRED:
        if not customer.is_verified:
            w = "User is not verified."
            logger.debug(w)
            raise Forbidden(message=w, status="user_not_verified")


def check_channel_acl(channel, customer):
    if channel in customer.blacklist_channels.all():
        w = "User is not allowed to login to this channel."
        logger.debug(w)
        raise Forbidden(message=w, status="user_not_allowed_in_channel")


def _login_guard():
    """access' failed-login guard (``django_access.services.login_guard``); None without access — no limit."""
    if not access_installed():
        return None
    from django_access.services import login_guard

    return login_guard


def _throttled(request, exc: Throttled) -> JsonResponse:
    """The 429 of ``api/token/``: status, ``Retry-After`` and DRF's detail, in this API's envelope."""
    request.customer = None  # nothing for save_ip_and_country to record
    response = to_json_response(
        Response({"detail": str(exc.detail)}, status="ERR", message="throttled", status_code=429)
    )
    response["Retry-After"] = str(exc.wait)
    return response


def _obtain_pair(request, data: dict) -> TokenObtainPairSerializer:
    """The checked token pair; with access, a blocked login raises ``Throttled`` before the password is checked."""
    username, guard = str(data.get("email") or "").strip(), _login_guard()
    if guard:
        guard.refuse_when_blocked(request, username)
    serializer = TokenObtainPairSerializer(data=dict(username=data.get("email"), password=data.get("password")))
    try:
        serializer.is_valid(raise_exception=True)
    except AuthenticationFailed as e:
        logger.exception(e)
        if guard:
            guard.record_failure(request, username)
        raise Forbidden(message="Incorrect username or password", status=e.get_full_details()["code"])
    except Exception as e:
        logger.exception(e)
        raise Forbidden(message="Got undefined error")
    if guard:
        guard.clear(request, username)
    return serializer


@api_view
@channel_view
@csrf_exempt
@require_http_method("POST")
@save_ip_and_country
def token_create(request, *args, **kwargs):
    try:
        serializer = _obtain_pair(request, json.loads(request.body))
    except Throttled as exc:
        return _throttled(request, exc)

    check_channel_acl(kwargs["channel"], serializer.user.customer)
    check_if_active(serializer.user.customer)
    check_if_verified(serializer.user.customer)

    tokens = serializer.validated_data
    uid = serializer.user.customer.uid
    request.customer = serializer.user.customer
    res_body = dict(customer_id=uid, **tokens)
    return Response(res_body, status="CREATED", message="token created successfully")


@api_view
@channel_view
@csrf_exempt
@require_http_method("POST")
@save_ip_and_country
def token_refresh(request, *args, **kwargs):
    data = json.loads(request.body)

    serializer_data = dict(refresh=data.get("refresh"))
    serializer = TokenRefreshSerializer(data=serializer_data)
    try:
        serializer.is_valid(raise_exception=False)
    except Exception as e:
        raise Forbidden(message=str(e))
    tokens = serializer.validated_data
    token_access = JWTAuthentication().get_validated_token(tokens["access"])
    user = JWTAuthentication().get_user(token_access)
    check_channel_acl(kwargs["channel"], user.customer)
    check_if_active(user.customer)
    check_if_verified(user.customer)
    uid = user.customer.uid
    request.customer = user.customer
    res_body = dict(customer_id=uid, **tokens)
    return Response(res_body)


@csrf_exempt
@api_view
@authenticate
@require_authentication
@require_http_method("POST")
def token_blacklist(request, *args, **kwargs):
    data = json.loads(request.body)
    refresh_token = data.get("refresh")
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(data={}, message="Refresh token blacklisted", status="BLACKLISTED")
    except TokenError as e:
        return Response(data={}, message=str(e), status="BLACKLISTED")


@api_view
@csrf_exempt
@require_http_method("POST")
def token_validate(request, *args, **kwargs):
    data = json.loads(request.body)
    try:
        # This rises exceptions if token is invalid
        token_obj = AccessToken(data.get("access"))
        serializer_data = dict(token=data.get("access"))
        serializer = TokenVerifySerializer(data=serializer_data)
        is_valid = serializer.is_valid()
        reason = serializer.errors
    except Exception as e:
        is_valid = False
        reason = {"access": str(e)}
    result = dict(is_valid=is_valid, reason=reason)
    return Response(result, status="VALIDATED", message="token validated successfully")
