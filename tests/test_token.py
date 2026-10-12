# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

JWT_BACKENDS = [
    "django_accounts.backends.JWTAccessBackend",
    "django.contrib.auth.backends.ModelBackend",
]


def _url(channel, name):
    return f"/api/accounts/v1/{channel.idx}/customer/{name}/"


def _create_token(api_client, channel, email, password):
    return api_client.post(_url(channel, "tokens"), {"email": email, "password": password}, format="json")


@pytest.mark.django_db
class TestTokenCreate:
    def test_customer_gets_tokens(self, api_client, customer, channel):
        response = _create_token(api_client, channel, "testuser@example.com", "Test1234!")

        assert response.status_code == 200
        assert response.json()["data"]["access"]

    def test_user_without_customer_is_403_not_500(self, api_client, admin_user, channel):
        response = _create_token(api_client, channel, "admin@example.com", "Admin1234!")

        assert response.status_code == 403
        assert response.json()["meta"]["status"] == "user_not_customer"

    def test_wrong_password_is_403(self, api_client, customer, channel):
        response = _create_token(api_client, channel, "testuser@example.com", "wrong")

        assert response.status_code == 403


@pytest.mark.django_db
class TestCustomerMeWithJWTBackend:
    """`@authenticate` views read the Bearer token only through JWTAccessBackend."""

    @pytest.fixture(autouse=True)
    def _jwt_backend(self, settings):
        settings.AUTHENTICATION_BACKENDS = JWT_BACKENDS

    def test_customer_token_is_accepted(self, api_client, customer, channel):
        access = _create_token(api_client, channel, "testuser@example.com", "Test1234!").json()["data"]["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = api_client.get(_url(channel, "me"))

        assert response.status_code == 200
        assert response.json()["data"]["email"] == "testuser@example.com"

    def test_no_token_is_401(self, api_client, channel):
        assert api_client.get(_url(channel, "me")).status_code == 401
