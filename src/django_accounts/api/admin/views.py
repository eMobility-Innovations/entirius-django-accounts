# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from django_accounts.api.admin.pagination import AdminPageNumberPagination
from django_accounts.schemas.responses.customer import CustomerListItem
from django_accounts.services import admin_service

_ADMIN_AUTH = [JWTAuthentication]
_ADMIN_PERMS = [IsAdminUser]

_BOOL_MAP = {"true": True, "false": False}


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return _BOOL_MAP.get(value.lower())


@extend_schema_view(
    list=extend_schema(
        summary="List customers",
        description="Paginated customer list with search and filters.",
        tags=["Customers"],
        responses=CustomerListItem,
        parameters=[
            OpenApiParameter(name="search", description="Search by email or name", type=str),
            OpenApiParameter(name="group", description="Filter by group code", type=str),
            OpenApiParameter(name="source_channel", description="Filter by source channel idx", type=str),
            OpenApiParameter(name="is_active", description="Filter by active status", type=bool),
            OpenApiParameter(name="is_verified", description="Filter by verification status", type=bool),
            OpenApiParameter(
                name="ordering",
                description="Sort field. Prefix - for descending.",
                type=str,
                enum=["created_at", "-created_at", "updated_at", "-updated_at", "email", "-email"],
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve customer by UID",
        description="Full customer profile with addresses, stats, and session info.",
        tags=["Customers"],
    ),
)
class CustomerViewSet(viewsets.ViewSet):
    authentication_classes = _ADMIN_AUTH
    permission_classes = _ADMIN_PERMS
    access_area = "accounts.customers"
    pagination_class = AdminPageNumberPagination

    def list(self, request: Request, **kwargs) -> Response:
        params = request.query_params
        qs = admin_service.list_customers(
            search=params.get("search"),
            group=params.get("group"),
            source_channel=params.get("source_channel"),
            is_active=_parse_bool(params.get("is_active")),
            is_verified=_parse_bool(params.get("is_verified")),
            ordering=params.get("ordering"),
        )
        page = self.paginator.paginate_queryset(qs, request)
        results = [admin_service.serialize_customer_list_item(c) for c in page]
        return self.paginator.get_paginated_response(results)

    def retrieve(self, request: Request, uid: str | None = None, **kwargs) -> Response:
        try:
            customer = admin_service.get_customer_detail(uid)
        except admin_service.CustomerNotFound as exc:
            raise NotFound(str(exc)) from exc
        return Response(admin_service.serialize_customer_detail(customer))

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator


@extend_schema_view(
    list=extend_schema(
        summary="List customer groups",
        description="All customer groups with customer counts.",
        tags=["Customer Groups"],
    )
)
class GroupViewSet(viewsets.ViewSet):
    authentication_classes = _ADMIN_AUTH
    permission_classes = _ADMIN_PERMS
    access_area = "accounts.customers"
    pagination_class = AdminPageNumberPagination

    def list(self, request: Request, **kwargs) -> Response:
        qs = admin_service.list_groups()
        page = self.paginator.paginate_queryset(qs, request)
        results = [admin_service.serialize_group(g) for g in page]
        return self.paginator.get_paginated_response(results)

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator


@extend_schema_view(
    list=extend_schema(
        summary="List accounts channels",
        description="All channels configured for the accounts module.",
        tags=["Accounts Channels"],
    )
)
class ChannelViewSet(viewsets.ViewSet):
    authentication_classes = _ADMIN_AUTH
    permission_classes = _ADMIN_PERMS
    access_area = "accounts.customers"
    pagination_class = AdminPageNumberPagination

    def list(self, request: Request, **kwargs) -> Response:
        qs = admin_service.list_channels()
        page = self.paginator.paginate_queryset(qs, request)
        results = [admin_service.serialize_channel(ch) for ch in page]
        return self.paginator.get_paginated_response(results)

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator
