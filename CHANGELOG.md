# Changelog

## Unreleased

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
