# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Profile (customer/<uid>/profile/) PATCH persists what GET returns."""

import json

import pytest
from django.test import Client
from rest_framework_simplejwt.tokens import RefreshToken

from django_accounts import settings as accounts_settings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _jwt_backend(settings):
    # The test settings authenticate with ModelBackend only; the v1 views need the customer JWT backend.
    settings.AUTHENTICATION_BACKENDS = ["django_accounts.backends.JWTAccessBackend"]


def _profile_url(channel, customer):
    return f"/{accounts_settings.PUBLIC_BASE_URL}/accounts/v1/{channel.idx}/customer/{customer.uid}/profile/"


def _client(customer):
    token = RefreshToken.for_user(customer.user).access_token
    return Client(HTTP_AUTHORIZATION=f"Bearer {token}")


def _patch(channel, customer, body):
    return _client(customer).patch(
        _profile_url(channel, customer), data=json.dumps(body), content_type="application/json"
    )


def _get(channel, customer):
    resp = _client(customer).get(_profile_url(channel, customer))
    assert resp.status_code == 200
    return resp.json()["data"]


class TestProfilePatch:
    def test_names_are_saved(self, channel, customer):
        resp = _patch(channel, customer, {"firstname": "Anna", "lastname": "Nowak"})

        assert resp.status_code == 200
        data = _get(channel, customer)
        assert data["firstname"] == "Anna"
        assert data["lastname"] == "Nowak"

    def test_sex_is_saved(self, channel, customer):
        resp = _patch(channel, customer, {"sex": "female"})

        assert resp.status_code == 200
        assert _get(channel, customer)["sex"] == "female"

    def test_omitted_fields_keep_their_values(self, channel, customer):
        _patch(channel, customer, {"firstname": "Anna"})

        data = _get(channel, customer)
        assert data["firstname"] == "Anna"
        assert data["lastname"] == "Doe"

    def test_invalid_sex_is_rejected(self, channel, customer):
        resp = _patch(channel, customer, {"sex": "robot"})

        assert resp.status_code == 400
        assert _get(channel, customer)["sex"] is None
