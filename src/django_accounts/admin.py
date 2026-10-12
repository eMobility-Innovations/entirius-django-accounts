# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import logging

from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib import admin, messages
from django.db import transaction
from django_admin_inline_paginator.admin import TabularInlinePaginated
from rest_framework_simplejwt.token_blacklist import models as blacklist_models

from django_accounts import settings
from django_accounts.models import Group, ProductRepresentation, Wishlist, WishlistProduct
from django_accounts.utils.api_keys import access_installed, mask_key

from .models import Address, AddressFile, APIAdminKey, Channel, Customer, File, Revoke, SocialLoginProviders

logger = logging.getLogger(__name__)


@admin.register(APIAdminKey)
class APIAdminKeyAdmin(admin.ModelAdmin):
    """Keys show only their last four characters; with django_access installed they are read-only (tokens rule)."""

    model = APIAdminKey
    list_display = ["channel", "masked_key"]
    list_filter = ("channel",)
    exclude = ("key",)
    readonly_fields = ("masked_key",)

    @admin.display(description="key")
    def masked_key(self, obj) -> str:
        return mask_key(obj.key)

    def has_add_permission(self, request) -> bool:
        return not access_installed() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None) -> bool:
        return not access_installed() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None) -> bool:
        return not access_installed() and super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change) -> None:
        super().save_model(request, obj, form, change)
        if not change:
            messages.warning(
                request,
                f"Key {mask_key(obj.key)} created; the full key is never shown here. "
                "Prefer `manage.py generate-api-admin-key <channel_idx>`, which prints it.",
            )


class AddressInline(admin.TabularInline):
    model = Address
    readonly_fields = ["id"]
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    inlines = [AddressInline]
    list_display = [
        "user",
        "source_channel",
        "email",
        "group",
        "uid",
        "external_id",
        "is_active",
        "is_verified",
        "phone",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_active", "is_verified", "source_channel", "group", "blacklist_channels"]
    search_fields = ["user__email"]
    autocomplete_fields = ["user", "shipping_address", "billing_address"]
    ordering = ("-updated_at",)

    actions = ["delete_customers"]

    def _delete_customer(self, request, customer: Customer):
        """Replicates API customer_delete logic in admin: blacklist tokens, delete addresses, customer and user."""
        user = customer.user
        with transaction.atomic():
            tokens_to_blacklist = blacklist_models.OutstandingToken.objects.filter(
                user=user, blacklistedtoken__isnull=True
            )
            if tokens_to_blacklist.exists():
                blacklist = [blacklist_models.BlacklistedToken(token=token) for token in tokens_to_blacklist]
                blacklist_models.BlacklistedToken.objects.bulk_create(blacklist)

            Address.objects.filter(customer=customer).delete()
            customer.delete()
            user.delete()

    def delete_model(self, request, obj: Customer):
        try:
            self._delete_customer(request, obj)
            self.message_user(request, f"Customer {obj} deleted successfully.")
        except Exception as e:
            self.logger.exception("Error deleting customer from admin: %s", e)
            self.message_user(request, f"Failed to delete customer {obj}: {e}", level=messages.ERROR)

    def delete_queryset(self, request, queryset):
        if not request.user.is_superuser:
            max_batch = settings.ADMIN_DELETE_CUSTOMER_MAX_BATCH
            count = queryset.count()
            if count > max_batch:
                self.message_user(
                    request,
                    f"Cannot delete {count} customers at once. Limit is {max_batch}. Please select fewer records.",
                    level=messages.ERROR,
                )
                return

        success = 0
        failed = 0
        for customer in queryset:
            try:
                self._delete_customer(request, customer)
                success += 1
            except Exception as e:
                failed += 1
                logger.exception("Error deleting customer %s from admin bulk: %s", customer, e)
        if success:
            self.message_user(request, f"Successfully deleted {success} customers.")
        if failed:
            self.message_user(request, f"Failed to delete {failed} customers.", level=messages.ERROR)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions

    def delete_customers(self, request, queryset):
        """Admin action to delete selected customers using custom logic."""
        return self.delete_queryset(request, queryset)

    delete_customers.short_description = "Delete selected customers (with token blacklist and cleanup)"
    delete_customers.allowed_permissions = ("view",)

    def save_model(self, request, obj, form, change):
        obj.check_blacklist()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.check_blacklist()


@admin.register(Revoke)
class RevokeAdmin(admin.ModelAdmin):
    fields = ["user", "created_at"]
    readonly_fields = ["user", "created_at"]


@admin.register(SocialLoginProviders)
class SocialLoginProviderAdmin(admin.ModelAdmin):
    list_display = ["provider", "name", "client_id", "key", "callback_url", "front_url"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = [
        "customer",
        "firstname",
        "lastname",
        "street",
        "city",
        "postcode",
        "telephone",
        "dialling_code",
        "country_code",
        "is_company",
        "company",
        "tax_id",
        "external_id",
        "source",
    ]
    search_fields = ["customer__user__email", "customer__uid", "firstname", "lastname", "company", "external_id"]
    list_filter = ["source"]
    autocomplete_fields = ["customer"]
    readonly_fields = ["id"]


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ["customer", "file_type", "name", "label"]


@admin.register(AddressFile)
class AddressFileAdmin(admin.ModelAdmin):
    list_display = ["customer", "name", "label", "address"]


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["idx", "label", "language"]


class WishlistProductInline(TabularInlinePaginated):
    model = WishlistProduct
    readonly_fields = ["created_at", "modified_at"]
    extra = 0
    raw_id_fields = ["product"]
    per_page = settings.WISHLIST_PRODUCT_PER_PAGE
    ordering = ("-modified_at",)


@admin.register(WishlistProduct)
class WishlistProductAdmin(admin.ModelAdmin):
    model = WishlistProduct
    list_display = ["wishlist", "product", "is_external", "extra", "sources"]
    list_filter = ["wishlist__channel"]
    search_fields = ["wishlist__uid", "product__sku"]
    autocomplete_fields = ["wishlist", "product"]
    ordering = ("-modified_at",)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    inlines = [WishlistProductInline]
    model = Wishlist
    list_filter = ("channel",)
    list_display = ["uid", "customer", "channel"]
    autocomplete_fields = ["customer"]
    search_fields = ["uid"]


@admin.register(ProductRepresentation)
class ProductRepresentationAdmin(admin.ModelAdmin):
    model = ProductRepresentation
    fields = ["sku", "name_t9n", "channel"]
    list_display = ["sku", "name_t9n", "channel"]
    list_filter = ["channel"]
    search_fields = ["sku", "name_t9n"]


admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    model = Group
    fields = ["code", "name", "is_active"]
    list_display = ["code", "name", "is_active", "created_at", "updated_at"]
    search_fields = ["code", "name"]
