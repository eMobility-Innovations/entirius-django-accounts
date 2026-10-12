# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import json

from django.core.handlers.wsgi import WSGIRequest
from django.views.decorators.csrf import csrf_exempt
from django_utils.api.decorators import require_http_method
from django_utils.api.exceptions import BadRequest, NotFound
from django_utils.api.responses import Response
from process_logger import ProcessLogger

from django_accounts.models import Customer
from django_accounts.services.customer import CustomerService
from django_accounts.utils.api_keys import erase_channel
from django_accounts.utils.decorators import admin_view

logger = ProcessLogger("ACCOUNTS_ADMIN_VIEW", module="django_accounts")


@admin_view
@csrf_exempt
@require_http_method("DELETE")
def admin_customer_delete(request: WSGIRequest, *args, **kwargs):
    """
    Endpoint to delete a customer account.
    Only the authenticated admin can delete account.
    After deletion, all tokens are blacklisted.
    """

    try:
        data = json.loads(request.body)
        email = data.get("email")
        if not email:
            raise BadRequest(message="Email is required")
    except json.JSONDecodeError:
        raise BadRequest(message="Invalid JSON in request body")

    customers = Customer.objects.filter(user__email=email)
    if (channel := erase_channel(request)) is not None:
        customers = customers.filter(source_channel=channel)
    if not customers.exists():
        raise NotFound(message="Customer account not found")

    customer_service = CustomerService()
    customer_service.set_logger(logger)

    success = []
    uids_success = []
    uids_failed = []
    for customer in customers:
        is_success, uid = customer_service.delete_customer(customer)
        if is_success:
            success.append(True)
            uids_success.append(uid)
        else:
            success.append(False)
            uids_failed.append(uid)

    if all(success):
        return Response(data={"deleted": True, "uid_ok": uids_success}, message="Customer account successfully deleted")
    else:
        raise BadRequest(
            data={"deleted": False, "uid_fail": uids_failed, "uid_ok": uids_success},
            message="Failed to delete customer account",
        )
