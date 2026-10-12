# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import secrets

import pytest
from allauth.account.models import EmailAddress
from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django_accounts.models import Address, Channel, Customer, Group, Wishlist
from django_accounts.models.product_representation import ProductRepresentation
from django_accounts.models.wishlist import WishlistProduct

User = get_user_model()


def import_keys_into_access() -> None:
    """With django_access installed keys are tokens: import the legacy rows as a deploy's migrate does."""
    if apps.is_installed("django_access"):
        from django_access.services.legacy import import_legacy_keys

        import_legacy_keys()


@pytest.fixture
def language(db):
    """Create a Language record (from django_regional)."""
    from django_regional.models import Language

    lang, _ = Language.objects.get_or_create(
        iso2="en",
        defaults={"iso3": "eng", "name_en": "English", "name_pl": "Angielski"},
    )
    return lang


@pytest.fixture
def channel(db, language):
    """Create a test Channel."""
    return Channel.objects.create(
        idx="test-channel",
        label="Test Channel",
        language=language,
    )


@pytest.fixture
def second_channel(db, language):
    """Create a second Channel for multi-channel tests."""
    return Channel.objects.create(
        idx="second-channel",
        label="Second Channel",
        language=language,
    )


@pytest.fixture
def group(db):
    """Create a customer Group."""
    return Group.objects.create(
        code="vip",
        name="VIP Customers",
        is_active=True,
    )


@pytest.fixture
def user(db):
    """Create a Django User."""
    return User.objects.create_user(
        username="testuser@example.com",
        email="testuser@example.com",
        password="Test1234!",
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def user_with_email(user):
    """Create a User with a verified allauth EmailAddress."""
    EmailAddress.objects.create(
        user=user,
        email=user.email,
        primary=True,
        verified=True,
    )
    return user


@pytest.fixture
def customer(user_with_email, channel):
    """Create a Customer linked to a User."""
    return Customer.objects.create(
        user=user_with_email,
        is_active=True,
        is_verified=True,
        source_channel=channel,
    )


@pytest.fixture
def address(customer):
    """Create a standard personal Address linked to the customer fixture."""
    return Address.objects.create(
        customer=customer,
        firstname="John",
        lastname="Doe",
        street="Main St 1",
        city="Warsaw",
        postcode="00-001",
        telephone="123456789",
        dialling_code="+48",
        country_code="PL",
    )


@pytest.fixture
def admin_user(db):
    """Create a staff/superuser."""
    return User.objects.create_superuser(
        username="admin@example.com",
        email="admin@example.com",
        password="Admin1234!",
    )


@pytest.fixture
def api_client():
    """Unauthenticated API client."""
    return APIClient()


@pytest.fixture
def admin_client(admin_user):
    """API client authenticated as admin."""
    client = APIClient()
    token = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def admin_client_session(admin_user, client):
    """Django test client logged in as the superuser (admin site pages)."""
    client.force_login(admin_user)
    return client


@pytest.fixture
def regular_client(user):
    """API client authenticated as non-admin user."""
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def second_address(customer):
    """Create a second address for the customer."""
    return Address.objects.create(
        customer=customer,
        firstname="Anna",
        lastname="Nowak",
        street="Krakowska 10",
        city="Krakow",
        postcode="30-001",
        telephone="987654321",
        dialling_code="+48",
        country_code="PL",
        company="ACME Sp. z o.o.",
        is_company=True,
        tax_id="PL1234567890",
    )


@pytest.fixture
def customer_with_addresses(customer, address, second_address):
    """Customer with 2 addresses and billing/shipping defaults set."""
    customer.billing_address = address
    customer.shipping_address = second_address
    customer.save()
    return customer


@pytest.fixture
def customer_with_details(customer_with_addresses, group):
    """Customer with group, phone, and area_code set."""
    c = customer_with_addresses
    c.group = group
    c.phone = "500500500"
    c.area_code = "+48"
    c.sex = "male"
    c.save()
    return c


@pytest.fixture
def wishlist_with_products(customer, channel):
    """Customer with a wishlist containing 2 products."""
    pr1 = ProductRepresentation.objects.create(sku="WISH-001", channel=channel)
    pr2 = ProductRepresentation.objects.create(sku="WISH-002", channel=channel)
    wl = Wishlist.objects.create(customer=customer, channel=channel)
    WishlistProduct.objects.create(wishlist=wl, product=pr1)
    WishlistProduct.objects.create(wishlist=wl, product=pr2)
    return customer


@pytest.fixture
def make_api_key(db):
    """Create an X-API-ADMIN-KEY the module accepts today and return its raw value.

    accounts has one key kind (``APIAdminKey``, customer erase), so ``scope`` is accepted and ignored. The key
    contract tests go through this helper only (with django_access installed it also imports the key as a legacy
    token), so moving the check onto another key store changes this function,
    never the assertions. Values are random and never printed.
    """
    from django_accounts.models import APIAdminKey

    def make_api_key(channel=None, scope: str | None = None) -> str:
        raw = secrets.token_hex(32)
        APIAdminKey.objects.create(channel=channel, key=raw)
        import_keys_into_access()
        return raw

    return make_api_key
