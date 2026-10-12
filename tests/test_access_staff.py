# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A staff account created through django-access gets the Customer row the CMS login (``customer/tokens/``) reads."""

import os
from unittest.mock import patch

import pytest

if os.environ.get("ENTIRIUS_TEST_NO_ACCESS"):
    pytest.skip("legacy path run", allow_module_level=True)
pytest.importorskip("django_access")

from allauth.account.models import EmailAddress  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django_access.services.access_service import Actor, StaffInput, create_staff_user  # noqa: E402
from django_access.signals import staff_user_created  # noqa: E402

from django_accounts.models import Customer  # noqa: E402

EMAIL, PASSWORD = "new.staff@example.com", "Staff1234!"
LOGIN_URL = "/api/accounts/1/test-channel/customer/tokens/"


@pytest.fixture
def staff(db):
    """The username is the e-mail: the module's test settings log in through ModelBackend by username."""
    user, _ = create_staff_user(StaffInput(username=EMAIL, email=EMAIL, role="viewer", password=PASSWORD), Actor())
    return user


@pytest.mark.django_db
class TestStaffCustomer:
    def test_new_staff_gets_an_active_verified_customer(self, staff):
        customer = Customer.objects.get(user=staff)
        assert (customer.is_active, customer.is_verified, customer.language) == (True, True, None)
        address = EmailAddress.objects.get(user=staff)
        assert (address.email, address.verified, address.primary) == (EMAIL, True, True)

    def test_new_staff_logs_in_through_customer_tokens(self, channel, staff, api_client):
        response = api_client.post(LOGIN_URL, {"email": EMAIL, "password": PASSWORD}, format="json")
        assert response.status_code == 200, response.content
        assert response.json()["data"]["customer_id"] == str(staff.customer.uid)

    def test_a_second_signal_creates_nothing(self, staff):
        staff_user_created.send(sender=type(staff), user=staff, actor=Actor())
        assert Customer.objects.filter(user=staff).count() == 1
        assert EmailAddress.objects.filter(user=staff).count() == 1

    def test_a_receiver_error_rolls_the_account_back(self):
        with patch("django_accounts.receivers.Customer.objects.get_or_create", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                create_staff_user(StaffInput(username=EMAIL, email=EMAIL, role="viewer"), Actor())
        assert not get_user_model().objects.filter(username=EMAIL).exists()
