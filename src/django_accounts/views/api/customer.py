# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json
import logging
from json import JSONDecodeError

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import get_password_validators, validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django_email.service.accounts.new_account import NewAccountEmail
from django_email.service.accounts.reset_password import ResetPasswordEmail
from django_regional.models import Language
from django_utils.api.decorators import (
    api_view,
    authenticate,
    parse_body,
    require_authentication,
    require_http_method,
    verify_captcha,
)
from django_utils.api.exceptions import BadRequest, Forbidden
from django_utils.api.responses import Response
from process_logger import ProcessLogger

from django_accounts import settings
from django_accounts.models import Channel, Customer
from django_accounts.services.customer import CustomerService
from django_accounts.utils.change_password import EmailChangePasswordHMAC
from django_accounts.utils.decorators import channel_view
from django_accounts.utils.params import PatchProfileRequestData, ResetPasswordRequestData
from django_accounts.utils.redirect_url import get_redirect_url

logger = logging.getLogger(__name__)
process_logger = ProcessLogger("ACCOUNTS_CUSTOMER_VIEW", module="django_accounts")


@api_view
@authenticate
@require_authentication
@require_http_method("GET")
def customer_me(request, *args, **kwargs):
    user = request.user

    resp_data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "groups": [elem.name for elem in user.groups.all()],
        "is_active": user.is_active,
    }

    return Response(resp_data)


@api_view
@csrf_exempt
@authenticate
@require_authentication
@require_http_method("GET", "PATCH")
def customer_profile(request, uid=None, *args, **kwargs):
    def get(request, uid=None, *args, **kwargs):
        try:
            extra_data = customer.extra
            if settings.SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API and customer.extra:
                extra_data = {
                    k: v for (k, v) in customer.extra.items() if k in settings.SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API
                }

            email_obj = customer.email
            res_body = dict(
                customer_id=customer_uid,
                firstname=customer.first_name,
                lastname=customer.last_name,
                email=email_obj.email if email_obj else request.user.email,
                sex=customer.sex,
                language=customer.language.iso2 if customer.language else None,
                extra=extra_data,
            )

            return Response(data=res_body)
        except JSONDecodeError as e:
            raise Forbidden(message=e.msg, status="invalid_json")

    @parse_body(PatchProfileRequestData.Schema)
    def patch(request, uid=None, *args, **kwargs):
        try:
            data = json.loads(request.body)
            logger.info("PATCH profile uid=%s fields=%s", uid, [k for k in data if k != "extra"])
            user_dirty = False
            customer_dirty = False

            for field in ["firstname", "lastname", "sex", "language"]:
                if data.get(field) is not None:
                    setattr(request.user, field, data.get(field))
                    user_dirty = True

            if "extra" in data and isinstance(data["extra"], dict):
                whitelist = settings.SPECIFY_KEYS_EXTRA_PROFILE_DATA_IN_API
                if whitelist:
                    current_extra = customer.extra or {}
                    current_extra.update({k: v for k, v in data["extra"].items() if k in whitelist})
                    customer.extra = current_extra
                    customer_dirty = True

        except JSONDecodeError as e:
            raise Forbidden(message=e.msg, status="invalid_json")

        if user_dirty:
            request.user.save()
        if customer_dirty:
            customer.save()
        data = {"message": "profile successfully updated"}
        return Response(data=data)

    customer = request.user.customer
    customer_uid = str(customer.uid)
    if customer_uid != uid:
        msg = "User with this uid don't exists"
        logger.warning(msg)
        raise Forbidden(message=msg, status="no_user")
    else:
        if request.method == "GET":
            return get(request, *args, **kwargs)
        else:
            return patch(request, *args, **kwargs)


def customer_create(request, user, phone, area_code, created_at, updated_at, language, is_active, channel):
    customer = Customer.objects.create_from_user(
        user, phone, area_code, is_active, created_at, updated_at, language, channel=channel
    )
    customer.save()

    blacklist_channels = settings.ACCOUNTS_CHANNEL_BLACKLIST.get(channel.idx, [])
    bc = Channel.objects.filter(idx__in=blacklist_channels)
    for blacklist_channel in bc:
        customer.blacklist_channels.add(blacklist_channel)
    customer.check_blacklist()
    customer.save()

    return customer.uid


@api_view
@csrf_exempt
@channel_view
@verify_captcha
@require_http_method("POST")
def account_create(request, *args, **kwargs):
    channel = kwargs["channel"]
    try:
        data = json.loads(request.body)
        email = None if data.get("email") is None else data.get("email")
        password = None if data.get("password") is None else data.get("password")
        phone = None if data.get("phone") is None else data.get("phone")
        area_code = None if data.get("area_code") is None else data.get("area_code")
        created_at = None if data.get("created_at") is None else data.get("created_at")
        updated_at = None if data.get("updated_at") is None else data.get("updated_at")
        is_active = False if data.get("is_active") is None else data.get("is_active")
        language = None if data.get("language") is None else data.get("language")

        if email is None:
            e = "You should provide email"
            logger.warning(e)
            raise Forbidden(message=e, status="no_email")

        if password is None:
            e = "You should provide password"
            logger.warning(e)
            raise Forbidden(status="no_password", message=e)

        if language is None:
            e = "You should provide language"
            logger.warning(e)
            raise Forbidden(message=e, status="no_language")

        if email is not None:
            try:
                validate_email(email)
                email = email.lower()
            except ValidationError as e:
                er = list(e)[0]
                raise Forbidden(message=er, status="invalid_email")

        try:
            pass_valid = get_password_validators(settings.AUTH_PASSWORD_ACCOUNT_VALIDATORS)
            validate_password(password, password_validators=pass_valid)
        except ValidationError as e:
            er = list(e)[0]
            err = e.error_list[0]
            raise Forbidden(message=er, status=err.code)

    except JSONDecodeError as e:
        raise Forbidden(message=e.msg, status="invalid_json")

    with transaction.atomic():
        existing_user = User.objects.filter(email=email).first()
        if existing_user is not None:
            customer = Customer.objects.get(user=existing_user)
            source_channel_idx = customer.source_channel.idx if customer and customer.source_channel else None
            e = f"User with this email exists on channel {source_channel_idx}"
            raise Forbidden(message=e, status="email_exists", data={"channel": source_channel_idx})
        user = User.objects.create_user(username=email, email=email, password=password)
        user.save()
        data["username"] = None
        user_email = EmailAddress(user=user, email=email)
        user_email.save()
        lang = Language.objects.get(iso2=language)

        if settings.EMAIL_DOUBLE_OPTIN:
            uid = customer_create(request, user, phone, area_code, created_at, updated_at, lang, is_active, channel)
            confirmation = EmailConfirmationHMAC(user_email)
            main_url = settings.NEW_ACCOUNT_REDIRECT_URL
            main_url = get_redirect_url(main_url, lang.iso2, channel.idx, channel.language.iso2)

            param_key = settings.NEW_ACCOUNT_REDIRECT_URL_PARAM_KEY
            param_uid = settings.NEW_ACCOUNT_REDIRECT_URL_PARAM_UID

            confirmation_link = f"{main_url}?{param_key}={confirmation.key}&{param_uid}={uid}"

            # send email
            new_account_email = NewAccountEmail(
                exception_type=NewAccountEmail.ExceptionType.API, language=lang.iso2, channel_idx=channel.idx
            )
            new_account_email.send([email], user.username, confirmation_link)

        else:
            confirmation = EmailConfirmationHMAC(user_email)
            confirmation_key = EmailConfirmationHMAC.from_key(confirmation.key)
            confirmation_key.confirm(request)
            uid = customer_create(
                request,
                user,
                phone,
                area_code,
                created_at,
                updated_at,
                lang,
                is_active=settings.ACCOUNTS_CUSTOMER_IS_ACTIVE_WITHOUT_DOUBLE_OPTIN,
                channel=channel,
            )

        data_res = json.loads(request.body)
        # The response echoes the request: never send the plaintext password back.
        data_res.pop("password", None)
        if settings.EMAIL_DOUBLE_OPTIN:
            data_res["confirmation_key"] = confirmation.key
        data_res["uid"] = uid
    return Response(data_res, status="CREATED", message="account created successfully")


@api_view
@csrf_exempt
@require_http_method("POST")
def customer_create_confirm(request, uid, *args, **kwargs):
    try:
        data = request.GET
        key = data.get("key")
        confirmation = EmailConfirmationHMAC.from_key(key)
        if confirmation is not None:
            confirmation.confirm(request)
            customer = Customer.objects.get(uid=uid)
            customer.is_active = True
            customer.save()
        else:
            e = "Invalid key"
            raise Forbidden(message=e, status="invalid_key")
        data = {"message": "Your account has been successfully verified"}
        return Response(data)
    except Exception as e:
        e = "Invalid key"
        raise Forbidden(message=e, status="invalid_key")


@api_view
@csrf_exempt
@channel_view
@require_http_method("POST")
@parse_body(ResetPasswordRequestData.Schema)
def customer_reset_password(request, *args, **kwargs):
    channel = kwargs["channel"]
    try:
        data = json.loads(request.body)
    except JSONDecodeError as e:
        raise Forbidden(message=e.msg)

    email = (
        EmailAddress.objects.select_related("user__customer__language")
        .filter(email=data.get("email"), user__customer__isnull=False)
        .first()
    )

    if email is None:
        e = "There exists no account with these credentials"
        raise Forbidden(message=e, status="wrong_account")

    user = email.user
    customer = user.customer
    lang = customer.language
    lang_iso2 = lang.iso2 if lang else (channel.language.iso2 if channel.language else settings.T9N_DEFAULT_LANG)
    channel_lang_iso2 = channel.language.iso2 if channel.language else lang_iso2

    if user.is_staff and settings.CMS_RESET_PASSWORD_REDIRECT_URL:
        main_url = settings.CMS_RESET_PASSWORD_REDIRECT_URL
    else:
        main_url = settings.RESET_PASSWORD_REDIRECT_URL
    main_url = get_redirect_url(main_url, lang_iso2, channel.idx, channel_lang_iso2)

    param_key = settings.RESET_PASSWORD_REDIRECT_URL_PARAM_KEY
    confirmation = EmailChangePasswordHMAC(email)
    confirmation_link = f"{main_url}?{param_key}={confirmation.key}"

    # send email
    reset_password_email = ResetPasswordEmail(
        exception_type=ResetPasswordEmail.ExceptionType.API, language=lang_iso2, channel_idx=channel.idx
    )
    reset_password_email.send([email.email], confirmation_link)

    return Response({"message": "Password confirmation link has been send to mail successfully"})


@api_view
@csrf_exempt
@require_http_method("POST")
def customer_reset_password_confirm(request, key=None, *args, **kwargs):
    confirmation = EmailChangePasswordHMAC.from_key(key)
    if confirmation is None:
        raise Forbidden(message="This reset link is invalid or has expired", status="invalid_key")

    try:
        data = json.loads(request.body)
    except JSONDecodeError as e:
        raise Forbidden(message=e.msg, status="invalid_json")

    new_are_same = data.get("new_password") == data.get("new_password_check")

    try:
        pass_valid = get_password_validators(settings.AUTH_PASSWORD_ACCOUNT_VALIDATORS)
        validate_password(data.get("new_password"), password_validators=pass_valid)
    except ValidationError as e:
        er = list(e)[0]
        err = e.error_list[0]
        raise Forbidden(message=er, status=err.code)

    if not new_are_same:
        e = "passwords do not match"
        raise Forbidden(message=e, status="pw_dont_match")
    else:
        user = confirmation.email_address.user
        with transaction.atomic():
            user.set_password(data.get("new_password"))
            user.save()
        return Response({"message": "Your password has been reset successfully"})


@api_view
@csrf_exempt
@authenticate
@require_authentication
@require_http_method("POST")
def customer_change_password(request, *args, **kwargs):
    try:
        data = json.loads(request.body)
    except JSONDecodeError as e:
        raise Forbidden(message=e.msg, status="invalid_json")

    new_are_same = data.get("new_password") == data.get("new_password_check")
    old_is_valid = request.user.check_password(data.get("old_password"))

    try:
        pass_valid = get_password_validators(settings.AUTH_PASSWORD_ACCOUNT_VALIDATORS)
        validate_password(data.get("new_password"), password_validators=pass_valid)
    except ValidationError as e:
        er = list(e)[0]
        err = e.error_list[0]
        raise Forbidden(message=er, status=err.code)

    if not old_is_valid:
        e = "Old password is invalid"
        logger.warning(e)
        raise Forbidden(message=e, status="old_pw_invalid")
    elif not new_are_same:
        e = "New passwords must match"
        logger.warning(e)
        raise Forbidden(message=e, status="new_pw_dont_match")
    else:
        with transaction.atomic():
            request.user.set_password(data.get("new_password"))
            request.user.save()
        return Response({"message": "Your password has been changed successfully"})


@api_view
@csrf_exempt
@authenticate
@require_authentication
@require_http_method("DELETE")
def customer_delete(request, uid=None, *args, **kwargs):
    """
    Endpoint to delete a customer account.
    Only the authenticated customer can delete their own account.
    After deletion, all tokens are blacklisted.
    """
    customer = request.user.customer
    customer_uid = str(customer.uid)

    if customer_uid != uid:
        msg = "User can only delete their own account"
        logger.error(msg)
        raise Forbidden(message=msg, status="unauthorized_deletion")

    customer_service = CustomerService()
    customer_service.set_logger(process_logger)
    success, _ = customer_service.delete_customer(customer)
    if success:
        return Response(data={"deleted": True, "uid": customer_uid}, message="Customer account successfully deleted")
    else:
        raise BadRequest(message="Failed to delete customer account", status="deletion_failed")
