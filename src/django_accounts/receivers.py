# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Receivers of other modules' signals; connected in ``AccountsConfig.ready()`` only when the sender is installed."""

from django_accounts.models import Customer


def create_staff_customer(sender, user, **kwargs) -> None:
    """``django_access.signals.staff_user_created``: the rows the CMS login (``customer/tokens/``) reads.

    Runs inside the access transaction: an exception rolls the new account back, so it is left to raise.
    """
    from allauth.account.models import EmailAddress  # lazy: a host may install accounts without allauth.account

    Customer.objects.get_or_create(user=user, defaults={"is_active": True, "is_verified": True})
    EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={"verified": True, "primary": True})
