# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import base64
import json
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from allauth.account.models import EmailAddress
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django_utils.api.decorators import api_view, parse_parameters
from django_utils.api.exceptions import BadRequest, Forbidden
from django_utils.api.responses import Response
from rest_framework_simplejwt.tokens import RefreshToken

from django_accounts.dto.social_login import SocialLoginParams
from django_accounts.dto.social_login import (
    SocialLoginProviders as SocialLoginProvidersDTO,
)
from django_accounts.jwt import TokenAccessSocialLogin
from django_accounts.models import Customer
from django_accounts.models.socials import SocialLoginProviders
from django_accounts.services.accounts_service import random_password

User = get_user_model()
import logging

from django.contrib import auth
from django.views.decorators.csrf import csrf_exempt
from marshmallow_dataclass import dataclass

from django_accounts.models import Channel
from django_accounts.utils.decorators import channel_view

logger = logging.getLogger(__name__)


FACEBOOK_ADAPTER = FacebookOAuth2Adapter
GOOGLE_ADAPTER = GoogleOAuth2Adapter

ALLOWED_OAUTH_ERRORS = frozenset({"access_denied", "server_error", "temporarily_unavailable"})


@dataclass
class TokenParams:
    access_social: str


def get_objects_social_service(provider_name: str, channel: "Channel") -> SocialLoginProvidersDTO:
    """
    Retrieves the SocialLogin and SocialLoginProviders objects for the specified provider name.
    """
    provider_obj = SocialLoginProviders.objects.filter(provider=provider_name, channel=channel).first()
    if provider_obj is None:
        e = f"Social service {provider_name} doesnt exist in admin panel"
        raise BadRequest(status="no_service_defined", message=e)

    if not provider_obj.is_enabled:
        e = f"Social service {provider_name} is turn off"
        raise BadRequest(status="no_service_defined", message=e)

    return provider_obj


@api_view
@csrf_exempt
@channel_view
@parse_parameters(SocialLoginParams.Schema())
def login_via_provider(
    request, params: "SocialLoginParams" = SocialLoginParams(lang="pl"), provider_name=None, *args, **kwargs
):
    channel = kwargs["channel"]
    try:
        channel = Channel.objects.get(idx=channel.idx)
    except Channel.DoesNotExist:
        raise BadRequest(status="no_channel", message="Channel doesnt exist")
    if provider_name == "facebook":
        provider = get_objects_social_service(provider_name, channel)
        if provider.is_enabled:
            return facebook_login(request, provider, params)
        else:
            e = f"Social logging by {provider_name} is off in admin panel"
            logger.warning(e)
            raise BadRequest(status="social_login_off", message=e)

    elif provider_name == "google":
        provider = get_objects_social_service(provider_name, channel)
        if provider.is_enabled:
            return google_login(request, provider, params)
        else:
            e = f"Social logging by {provider} is off in admin panel"
            logger.warning(e)
            raise BadRequest(status="social_login_off", message=e)
    else:
        e = f"There is no social login by {provider_name} defined"
        logger.warning(e)
        raise BadRequest(status="wrong_login_providers", message=e)


@api_view
@channel_view
@csrf_exempt
def callback_via_provider(
    request, params: SocialLoginParams = SocialLoginParams(lang="pl"), provider_name: str = None, *args, **kwargs
):
    """
    Checking if providers exists/is_enabled.
    Returns a function specified by the name of the provider.
    """
    channel = kwargs["channel"]
    try:
        channel = Channel.objects.get(idx=channel.idx)
    except Channel.DoesNotExist:
        raise BadRequest(status="no_channel", message="Channel doesnt exist")

    if provider_name not in ("facebook", "google"):
        e = f"There is no social login by {provider_name} defined"
        logger.warning(e)
        raise BadRequest(status="wrong_login_providers", message=e)

    provider = get_objects_social_service(provider_name, channel)
    if not provider.is_enabled:
        e = f"Social logging by {provider_name} is off"
        logger.warning(e)
        raise BadRequest(status="social_login_off", message=e)

    # OAuth2 error callback — user denied consent or provider error.
    # Redirect to frontend instead of returning raw JSON.
    oauth_error = request.GET.get("error")
    if oauth_error:
        return _handle_oauth_error(request, provider, oauth_error)

    if provider_name == "facebook":
        return facebook_login_callback(request, provider)
    return google_login_callback(request, provider)


def _encode_state(state_dict: dict) -> str:
    raw = json.dumps(state_dict, separators=(",", ":"), ensure_ascii=False)
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_state(state_str: str | None) -> dict:
    if not state_str:
        return {}
    try:
        raw = base64.urlsafe_b64decode(state_str.encode()).decode()
        return json.loads(raw)
    except Exception:
        return {}


def _get_front_url(front_url: dict, lang: str) -> str:
    """Return the URL for the given language, falling back to the first available value."""
    return front_url.get(lang) or next(iter(front_url.values()), "")


def _resolve_redirect_url(
    candidate: str | None, provider_front_url: str, allowed_origins: list[str] | None = None
) -> str:
    """Return an absolute, safe URL.

    - If candidate is None, return provider_front_url
    - If relative path, attach to provider_front_url's origin
    - If absolute URL, allow only if netloc matches provider_front_url or any of allowed_origins
    - Otherwise, fallback to provider_front_url
    """
    if not candidate:
        return provider_front_url
    try:
        parsed_candidate = urlparse(candidate)
        front_parsed = urlparse(provider_front_url)
        allowed_netlocs = {front_parsed.netloc}
        for origin in allowed_origins or []:
            parsed_origin = urlparse(origin)
            if parsed_origin.netloc:
                allowed_netlocs.add(parsed_origin.netloc)
        if not parsed_candidate.scheme and not parsed_candidate.netloc:
            path = parsed_candidate.path if parsed_candidate.path.startswith("/") else f"/{parsed_candidate.path}"
            rebuilt = parsed_candidate._replace(scheme=front_parsed.scheme, netloc=front_parsed.netloc, path=path)
            return urlunparse(rebuilt)
        if parsed_candidate.scheme in ("http", "https") and parsed_candidate.netloc in allowed_netlocs:
            return candidate
    except Exception:
        pass
    return provider_front_url


def _append_query_params(url: str, params: dict) -> str:
    p = urlparse(url)
    current_qs = parse_qs(p.query, keep_blank_values=True)
    for k, v in params.items():
        current_qs[k] = [v]
    new_query = urlencode(current_qs, doseq=True)
    return urlunparse(p._replace(query=new_query))


def _handle_oauth_error(request, provider, error_code: str):
    """Redirect to frontend with a safe error code when OAuth provider returns an error.

    Used when the user denies consent or the provider reports a server error.
    """
    lang = request.GET.get("lang", "")
    state = _decode_state(request.GET.get("state"))
    redirect_url_param = state.get("redirect_url")
    front_url = _get_front_url(provider.front_url, lang)
    final_redirect = _resolve_redirect_url(redirect_url_param, front_url, provider.allowed_origins)
    safe_error = error_code if error_code in ALLOWED_OAUTH_ERRORS else "provider_error"
    final_redirect = _append_query_params(final_redirect, {"error": safe_error})
    logger.info("OAuth error redirect: error=%s, redirect=%s", safe_error, final_redirect)
    return redirect(final_redirect)


def facebook_login(request, provider, params: SocialLoginParams | None = None):
    """
    Redirects the user to Facebook authorization page.
    """
    client_id = provider.client_id
    authorize_url = FACEBOOK_ADAPTER.provider_default_auth_url
    scope = ["email"]
    callback_url = provider.callback_url + f"?lang={provider.channel.language.iso2}"

    state_payload = {}
    if params and params.redirect_url:
        state_payload["redirect_url"] = params.redirect_url
    state = _encode_state(state_payload) if state_payload else None

    query = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "scope": ",".join(scope),
    }
    if state:
        query["state"] = state
    authorize_url = f"{authorize_url}?{urlencode(query)}"
    return redirect(authorize_url, data={})


def facebook_get_access_token(request, provider: SocialLoginProvidersDTO) -> str | None:
    """
    Retrieves an access token from Facebook.
    """
    code = request.GET.get("code")
    client_id = provider.client_id
    client_secret = provider.key
    token_url = "https://graph.facebook.com/v7.0/oauth/access_token"
    callback_url = provider.callback_url + f"?lang={provider.channel.language.iso2}"
    token_url = (
        f"{token_url}?client_id={client_id}&redirect_uri={callback_url}&client_secret={client_secret}&code={code}"
    )
    response = requests.get(token_url)
    response_dict = response.json()
    access_token = response_dict.get("access_token")
    if access_token is None:
        raise Forbidden
    return access_token


def facebook_get_client_info(access_token: str) -> dict:
    """
    Return client info processing GET request to Google
    """
    graph_url = "https://graph.facebook.com/v7.0/me"
    graph_url = f"{graph_url}?fields=id,name,email&access_token={access_token}"
    profile_response = requests.get(graph_url)
    profile_data = profile_response.json()
    return profile_data


def facebook_login_callback(request, provider):
    """
    Handles the callback from the Facebook OAuth 2.0 authorization process.
    Creating or updating objects User, EmailAddress, UserAccount, Customer
    If the user is not already created generate password.
    """
    access_token = facebook_get_access_token(request, provider)
    profile_data = facebook_get_client_info(access_token)
    user_data = auth.authenticate(request)
    lang = request.GET.get("lang", "")

    try:
        redirect_url_param = _decode_state(request.GET.get("state")).get("redirect_url")
    except Exception:
        redirect_url_param = None
    if user_data is None:
        with transaction.atomic():
            user, is_created_user = User.objects.update_or_create(
                email=profile_data["email"], defaults={"username": profile_data["email"]}
            )
            email_address, is_created_email_address = EmailAddress.objects.update_or_create(
                user=user, email=profile_data["email"]
            )
            customer, is_created_customer = Customer.objects.update_or_create(user=user)
            uid = user.customer.uid
            if is_created_user:
                user.set_password(random_password())
                user.save()

            refresh = RefreshToken.for_user(user)

            access_social = TokenAccessSocialLogin.helper.encode(
                TokenAccessSocialLogin.get_data(
                    refresh=str(refresh),
                    access=str(refresh.access_token),
                    issued_at=datetime.now(),
                    customer_id=str(uid),
                )
            )
            front_url = _get_front_url(provider.front_url, lang)
            final_redirect = _resolve_redirect_url(redirect_url_param, front_url, provider.allowed_origins)
            final_redirect = _append_query_params(final_redirect, {"access_social": access_social})
            return redirect(final_redirect)

    else:
        raise Forbidden(message="", status="")


def google_login(request, provider: SocialLoginProvidersDTO, params: SocialLoginParams | None = None):
    """
    Redirects the user to Google's OAuth 2.0 authorization page.
    """
    client_id = provider.client_id
    authorize_url = GOOGLE_ADAPTER.authorize_url
    scope = ["email"]
    callback_url = provider.callback_url + f"?lang={provider.channel.language.iso2}"

    state_payload = {}
    if params and params.redirect_url:
        state_payload["redirect_url"] = params.redirect_url
    state = _encode_state(state_payload) if state_payload else None

    query = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "scope": ",".join(scope),
        "response_type": "code",
    }
    if state:
        query["state"] = state

    authorize_url = f"{authorize_url}?{urlencode(query)}"
    return redirect(authorize_url, data={})


def google_get_access_token(request, provider: SocialLoginProvidersDTO) -> str | None:
    """
    Retrieves an access token from Google's OAuth 2.0 API.
    """
    code = request.GET.get("code")
    client_id = provider.client_id
    client_secret = provider.key
    token_url = GOOGLE_ADAPTER.access_token_url
    callback_url = provider.callback_url + f"?lang={provider.channel.language.iso2}"
    token_url = f"{token_url}?client_id={client_id}&client_secret={client_secret}&redirect_uri={callback_url}&code={code}&grant_type=authorization_code"
    response = requests.post(token_url)
    response_dict = response.json()
    access_token = response_dict.get("access_token")
    if access_token is None:
        raise Forbidden
    return access_token


def google_get_client_info(access_token: str) -> dict:
    """
    Return client info processing GET request to Google
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    profile_response = requests.get(profile_url, headers=headers)
    profile_data = profile_response.json()
    return profile_data


def google_login_callback(request, provider):
    """
    Handles the callback from the Google OAuth 2.0 authorization process.
    Creating or updating objects User, EmailAddress, UserAccount, Customer
    If the user is not already created generate password.
    """
    access_token = google_get_access_token(request, provider)
    profile_data = google_get_client_info(access_token)
    user_data = auth.authenticate(request)
    lang = request.GET.get("lang", "")

    try:
        redirect_url_param = _decode_state(request.GET.get("state")).get("redirect_url")
    except Exception:
        redirect_url_param = None

    if user_data is None:
        with transaction.atomic():
            user, is_created_user = User.objects.update_or_create(
                email=profile_data["email"], defaults={"username": profile_data["email"]}
            )
            email_address, is_created_email_address = EmailAddress.objects.update_or_create(
                user=user, email=profile_data["email"]
            )
            customer, is_created_customer = Customer.objects.update_or_create(user=user)
            uid = user.customer.uid
            if is_created_user:
                user.set_password(random_password())
                user.save()

            refresh = RefreshToken.for_user(user)

            access_social = TokenAccessSocialLogin.helper.encode(
                TokenAccessSocialLogin.get_data(
                    refresh=str(refresh),
                    access=str(refresh.access_token),
                    issued_at=datetime.now(),
                    customer_id=str(uid),
                )
            )
            front_url = _get_front_url(provider.front_url, lang)
            final_redirect = _resolve_redirect_url(redirect_url_param, front_url, provider.allowed_origins)
            final_redirect = _append_query_params(final_redirect, {"access_social": access_social})
            return redirect(final_redirect)

    else:
        raise Forbidden(message="", status="")


@api_view
@csrf_exempt
@parse_parameters(TokenParams.Schema())
def return_client_token(request, params: TokenParams, *args, **kwargs) -> "Response":
    try:
        token = params.access_social
        data = TokenAccessSocialLogin.helper.decode(token)
        is_expired = TokenAccessSocialLogin.verify_data(data)
    except Exception:
        raise BadRequest(status="FAIL", message="Token is expired or valid")
    if is_expired:
        raise BadRequest(status="FAIL", message="Token is expired")

    return Response(data=data)
