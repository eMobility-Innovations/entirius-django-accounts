# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import csv
import json
import logging
from typing import AnyStr

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.utils.crypto import get_random_string
from django_regional.models import Language

from django_accounts import settings
from django_accounts.enums import AddressesImportBy, AssignAddress
from django_accounts.models import Address, Channel, Customer, Group
from django_accounts.models.address import AddressSourceEnum

logger = logging.getLogger(__name__)


def read_from_csv(absolute_path: AnyStr, quotechar: str = '"') -> (list, AnyStr):
    if absolute_path is not None:
        path = absolute_path
    else:
        return [], "Need to define csv path"
    with open(path) as f:
        reader = csv.reader(f, delimiter=",", quotechar=quotechar)
        headers = next(reader, None)
        data = {}
        for h in headers:
            data[h] = []
        for row in reader:
            for h, v in zip(headers, row):
                data[h].append(v)
    return data, "Loaded"


_RANDOM_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ123456789[~!@#$%^&*()_+{}\":;'[]"


def random_password() -> str:
    """Password for an account the user never typed one for (Django 5 removed make_random_password)."""
    return get_random_string(20, _RANDOM_CHARS)


def create_user(email, name="", last_name=""):
    email = email.lower()
    user = User.objects.create_user(username=email, email=email, first_name=name, last_name=last_name)
    user.set_password(random_password())
    user.save()
    user_email = EmailAddress(user=user, email=email, verified=True, primary=True)
    user_email.save()
    return user


def map_bool(value, default: bool = True):
    if value == "1":
        return True
    elif value == "0":
        return False
    else:
        return default


def find_group_by_name(group_code) -> Group | None:
    try:
        group = Group.objects.get(name=str(group_code))
    except ObjectDoesNotExist:
        group = None
    return group


def create_customer(data, idx, user, channels_cache: dict[str, Channel] = None):
    phone = data.get("phone")[idx] if data.get("phone") is not None else ""
    area_code = data.get("area_code")[idx] if data.get("area_code") is not None else ""
    language_iso2 = data.get("language")[idx] if data.get("language") is not None else ""
    is_active = map_bool(data.get("is_active")[idx] if data.get("is_active") is not None else "")
    is_verified = map_bool(data.get("is_verified")[idx] if data.get("is_verified") is not None else "")
    external_id = data.get("external_id")[idx] if data.get("external_id") is not None else ""
    extra = data.get("extra")[idx] if data.get("extra") is not None else ""
    try:
        ext = json.loads(extra)
    except json.JSONDecodeError:
        ext = None
    group_name = data.get("group")[idx] if data.get("group") is not None else ""
    channel_idx = data.get("channel_idx")[idx] if data.get("channel_idx") is not None else None
    channel = channels_cache.get(channel_idx, None)
    customer = Customer.objects.create_from_user(
        user=user,
        phone=phone,
        area_code=area_code,
        is_active=is_active,
        is_verified=is_verified,
        language=Language.objects.get(iso2=language_iso2),
        external_id=external_id,
        extra=ext,
        group=find_group_by_name(group_name),
        channel=channel,
    )
    customer.save()

    blacklist_channels = settings.ACCOUNTS_CHANNEL_BLACKLIST.get(channel.idx, [])
    final_blacklist_channels = []
    for bc in blacklist_channels:
        if bc in channels_cache:
            final_blacklist_channels.append(channels_cache[bc])
    if final_blacklist_channels:
        customer.blacklist_channels.set(final_blacklist_channels)
        customer.check_blacklist()
        customer.save()


def creating_in_db_for_each_line(data):
    errors = 0
    number_accounts_csv = len(data.get("email"))
    for idx, each in enumerate(data.get("email")):
        email = each
        name = data.get("name")[idx] if data.get("name") is not None else ""
        last_name = data.get("last_name")[idx] if data.get("last_name") is not None else ""
        if email is None or email == "":
            e = "You should provide email"
            logger.warning(f"{e}")
            errors += 1
            continue

        if email is not None:
            try:
                validate_email(email)
                email = email.lower()

            except ValidationError as er:
                e = list(er)[0]
                logger.warning(f"{e}")
                errors += 1
                continue

        existing_user = User.objects.filter(email=email).first()
        if existing_user is not None:
            e = "Email exists"
            logger.warning(f"{e}")
            errors += 1
            continue

        user = create_user(email, name, last_name)
        channels = {channel.idx: channel for channel in Channel.objects.all()}
        create_customer(data, idx, user, channels_cache=channels)

    return errors, number_accounts_csv


def create_address(data, idx, customer):
    firstname = data.get("firstname")[idx] if data.get("firstname") is not None else None
    lastname = data.get("lastname")[idx] if data.get("lastname") is not None else None
    street = data.get("street")[idx] if data.get("street") is not None else None
    city = data.get("city")[idx] if data.get("city") is not None else None
    postcode = data.get("postcode")[idx] if data.get("postcode") is not None else None
    country_code = data.get("country_code")[idx] if data.get("country_code") is not None else None
    telephone = data.get("telephone")[idx] if data.get("telephone") is not None else None
    dialling_code = data.get("dialling_code")[idx] if data.get("dialling_code") is not None else None
    company = data.get("company")[idx] if data.get("company") is not None else None
    is_company = map_bool(data.get("is_company")[idx] if data.get("is_company") is not None else None, False)
    tax_id = data.get("tax_id")[idx] if data.get("tax_id") is not None else None
    external_id = data.get("address_id")[idx] if data.get("address_id") is not None else None
    address = Address(
        customer=customer,
        firstname=firstname,
        lastname=lastname,
        street=street,
        city=city,
        postcode=postcode,
        country_code=country_code,
        telephone=telephone,
        dialling_code=dialling_code,
        company=company,
        is_company=is_company,
        tax_id=tax_id,
        external_id=external_id,
        source=AddressSourceEnum.CSV,
    )
    address.save()
    return address


def creating_addresses_for_each_line(data, find_by: int = AddressesImportBy.EMAIL):
    errors = 0
    number_addresses_csv = len(data.get("email"))
    for idx, each in enumerate(data.get("email")):
        email = each.lower()
        external_id = data.get("external_id")[idx] if data.get("external_id") is not None else ""

        if find_by == AddressesImportBy.EMAIL:
            try:
                customer = Customer.objects.get(user__email=email)
            except ObjectDoesNotExist:
                e = f"Customer with email {email} not found"
                logger.warning(f"{e}")
                errors += 1
                continue
            except Exception as e:
                logger.exception(e)
                errors += 1
                continue
        elif find_by == AddressesImportBy.EXTERNAL_ID:
            try:
                customer = Customer.objects.get(external_id=external_id)
            except ObjectDoesNotExist:
                e = f"Customer with external_id {external_id} not found"
                logger.warning(f"{e}")
                errors += 1
                continue
        else:
            e = "Unknown find_by flag"
            logger.warning(f"{e}")
            raise Exception(e)
        try:
            address = create_address(data, idx, customer)
            assign = AssignAddress.map(data.get("assign")[idx] if data.get("assign") is not None else None, None)
            match assign:
                case AssignAddress.SHIPPING:
                    customer.shipping_address = address
                case AssignAddress.BILLING:
                    customer.billing_address = address
                case AssignAddress.BOTH:
                    customer.shipping_address = address
                    customer.billing_address = address

            customer.save()
        except Exception as e:
            logger.exception(e)
            errors += 1
            continue

    return errors, number_addresses_csv
