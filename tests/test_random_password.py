# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pytest

from django_accounts.services.accounts_service import create_user, random_password


def test_random_password_is_twenty_chars_and_varies():
    first, second = random_password(), random_password()
    assert len(first) == 20
    assert first != second


@pytest.mark.django_db
def test_create_user_sets_a_usable_password():
    user = create_user("Someone@Example.com", name="Some")
    assert user.username == "someone@example.com"
    assert user.has_usable_password()
