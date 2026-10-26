# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from allauth.account import app_settings
from allauth.account.models import EmailAddress
from django.contrib.auth.tokens import default_token_generator
from django.core import signing

# Not allauth's app_settings.SALT: its e-mail confirmation key signs the same e-mail address pk under that salt,
# so a signup confirmation link would be a password reset key too.
SALT = "django_accounts.password_reset"


class EmailChangePasswordHMAC:
    """Password reset key: the e-mail address pk and a Django password reset token, signed.

    The token hashes the user's password, so a key works once and stops working when the password changes another
    way.
    """

    def __init__(self, email_address):
        self.email_address = email_address

    @property
    def key(self):
        token = default_token_generator.make_token(self.email_address.user)
        return signing.dumps(obj={"email": self.email_address.pk, "token": token}, salt=SALT)

    @classmethod
    def from_key(cls, key):
        try:
            max_age = 60 * 60 * 24 * app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
            payload = signing.loads(key, max_age=max_age, salt=SALT)
            email_address = EmailAddress.objects.select_related("user").get(pk=payload["email"])
        except (signing.SignatureExpired, signing.BadSignature, EmailAddress.DoesNotExist):
            return None
        if not default_token_generator.check_token(email_address.user, payload["token"]):
            return None
        return EmailChangePasswordHMAC(email_address)
