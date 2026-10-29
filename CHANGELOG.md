# Changelog

## 6.0.2 — 2026-10-29

- Security: login, signup and password reset are throttled. Before, only `customer/tokens/` with `django_access`
  installed had a limit; signup and `customer/password/reset/` could be hammered for mail bombing and account
  enumeration, and a captcha is no defence (`django_captcha` is optional). Over the limit the endpoint answers 429
  with `Retry-After`, in the usual envelope (`meta.message` `throttled`). Scopes and default rates:

  | Endpoint | Scope | Default |
  |---|---|---|
  | `customer/tokens/` | `accounts_login_ip` | `30/min` per IP |
  | `customer/signup/` | `accounts_signup_ip` | `10/hour` per IP |
  | `customer/signup/` | `accounts_signup_email` | `3/hour` per email |
  | `customer/password/reset/` | `accounts_password_reset_ip` | `10/hour` per IP |
  | `customer/password/reset/` | `accounts_password_reset_email` | `3/hour` per email |

  Override a scope in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`; a missing or malformed value keeps the default
  (a throttle is never switched off by a typo). The per-email counters key on a SHA-256 of the lower-cased address,
  never the address. Counters live in the default Django cache: use a shared one (Redis) when the service runs
  several processes.
- Per-IP throttles resolve the client through `django_utils.api.client_ip`: behind Cloudflare or a load balancer set
  `CLIENT_IP_HEADER` (e.g. `"HTTP_CF_CONNECTING_IP"`) in the service, otherwise `REMOTE_ADDR` / `DRF_NUM_PROXIES`
  decide, and every visitor behind a proxy shares one counter. Trust the header only when the origin is reachable
  through that proxy alone.
- Requires `entirius-django-utils>=2.4.1`.

## 6.0.1 — 2026-10-27

- Security: the signup response no longer carries `confirmation_key`. With `EMAIL_DOUBLE_OPTIN` on, the caller got
  the key of the confirmation link and could activate an account on an address it does not own
  (`customer/signup/<uid>/?key=...`), without the mail. The key now reaches the customer only in the mail; the
  response keeps `uid`. A client that confirmed from the response (tests did) reads the link from the mail.
- Security: `customer/signup/<uid>/?key=...` activates only the customer the key's address belongs to. It confirmed
  the key's address and activated whichever `uid` the path named, so one's own key from one's own mail activated
  another customer (signup returns `uid`). A key of another address answers 403 `invalid_key`.
- Security: a password reset link works once. Its key was the signed e-mail address pk, so the same link set the
  password again and again for 3 days, and the signup confirmation key of allauth (the same pk under the same salt)
  was a valid reset key too. The key now carries a Django password reset token (bound to the password) and is
  signed under its own salt. Reset links sent before the upgrade stop working; the customer requests
  a new one.
- Docs: `RESET_PASSWORD_EMAIL_LIFETIME` was documented as the reset link's validity (7 days); the link never read
  it. A link expires after `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` or `PASSWORD_RESET_TIMEOUT` (3 days each by
  default), whichever comes first, and ends on a password change, an e-mail change or a login that records `last_login`.
- An unset `RESET_PASSWORD_REDIRECT_URL` (or `NEW_ACCOUNT_REDIRECT_URL` with `EMAIL_DOUBLE_OPTIN`) no longer
  surfaces as an unexplained 500: `customer/password/reset/` and `customer/signup/` answer 500 with
  `meta.status` `NOT_CONFIGURED`, log the missing setting and send no mail. A dict-shaped URL with no entry and no
  `"default"` for the customer's language/channel gets the same answer instead of a link with a dict in it.
- System checks `django_accounts.W001` (`RESET_PASSWORD_REDIRECT_URL` unset) and `django_accounts.W002`
  (`NEW_ACCOUNT_REDIRECT_URL` unset with `EMAIL_DOUBLE_OPTIN` on) warn at deploy time; warnings only, `migrate`
  still runs. Deployments without them must set the storefront URLs.
- Docs: `CMS_RESET_PASSWORD_REDIRECT_URL` (staff reset link to the admin CMS) and the dict shape of the redirect URLs.

## 6.0.0 — 2026-10-12

- Access: the module declares its own access areas on its AppConfig and its admin views (copied from the
  entirius-django-access defaults; behaviour unchanged).
- Keys verified by django-access when installed: the X-API-ADMIN-KEY erase route checks access tokens
  through `verify_api_key` (scope `accounts.erase`), never the legacy table. Without django-access
  nothing changes. `generate-api-admin-key` then refuses and names `access_token create`; the key admin
  becomes read-only.
- Without django-access the key admin shows a new key once on creation; with it, delete is blocked too.
- The key admin shows only the last four characters of a key.
- `customer/tokens/` (the CMS staff login) runs django-access' failed-login guard when installed: blocked per
  username + address and per address before the password is checked (429 with `Retry-After`, the counters and
  `AUTH_TOKEN_*` settings of the service's `api/token/`), a success clears the per-user counter. Without
  django-access nothing changes.
- The key admin's creation message masks the new key (a Django message is stored in a cookie).
- **Breaking for integrators:** with django-access, a channel-pinned erase token deletes only customers whose
  `source_channel` is the URL's channel (a customer without one is out of reach); an e-mail found only elsewhere
  answers the unknown-e-mail 404. Legacy erase keys are imported as tokens pinned to their channel, so after the
  upgrade they erase only there. An unpinned token, and the path without django-access, still erase in every channel.
- A staff account created through django-access (`staff_user_created`) gets its `Customer` (active, verified) and a
  verified primary e-mail address — the rows the CMS login on `customer/tokens/` reads.
- OpenAPI: the admin customer list is generated as `accounts_v2_admin_customers_list` and documents its
  paginated response. Metadata only.
- `customer/signup/` no longer echoes the plaintext password in its response (the rest of the request
  echo, `uid` and `confirmation_key` are unchanged).
- Fix `PATCH customer/<uid>/profile/` answering 200 without saving: `firstname` and
  `lastname` now land on the user's `first_name` / `last_name`, `sex` on the customer.
- `customer/tokens/` answers 403 `user_not_customer` instead of 500 when the login is valid but the
  user has no Customer profile (e.g. a staff-only account).
- Docs: `JWTAccessBackend` in `AUTHENTICATION_BACKENDS` is required for the customer endpoints.

## 5.0.1 — 2026-07-13

- Fix broken format string in the password validator help text.

## 5.0.0 — 2026-07-11

- Initial public release: the customer identity layer — registration with double
  opt-in, JWT authentication, password policy, social login (Google/Facebook),
  address book, channel-scoped wishlists, GDPR consent management, and
  channel-scoped admin API keys.
- Read-only admin API v2: customers list/detail, groups, channels — Pydantic
  response schemas with OpenAPI docs.
- Migrations squashed into a single initial migration for the Entirius epoch.
