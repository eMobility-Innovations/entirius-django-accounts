# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.apps import AppConfig, apps


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_accounts"
    verbose_name = "Accounts"
    is_volkanos = True
    # Copied 1:1 from entirius-django-access cf538d2 catalogue defaults;
    # the access defaults stay until this module's release.
    access_areas = [
        {
            "key": "accounts.customers",
            "label": "Customers and customer groups",
            "levels": ("read",),
            "sensitive": ("pii",),
        },
    ]
    access_token_scopes = [
        {
            "key": "accounts.erase",
            "label": "Delete a customer account (GDPR)",
            "publishable": False,
            "routes": ("/api-admin/accounts/{version}/{channel_idx}/customer/delete",),
        },
    ]
    # Every admin view carries its access_area; no route needs a path rule.
    access_route_rules = []

    def ready(self) -> None:
        if apps.is_installed("django_access"):
            from django_access.signals import staff_user_created

            from django_accounts.receivers import create_staff_customer

            staff_user_created.connect(create_staff_customer, dispatch_uid="django_accounts_staff_customer")
