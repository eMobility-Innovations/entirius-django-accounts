# AGENTS.md

`entirius-django-accounts` (Django app `django_accounts`) — customer authentication and account management module
of Entirius. Handles registration, JWT login, address book,
wishlist, social login (Google/Facebook), and CSV import/export.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |
| `make test-legacy` | test suite without django_access (legacy key path) |

Tests need PostgreSQL: set `DATABASE_URL` (the default in `tests/settings.py` points at a local postgres).

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_accounts` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Access: areas and token scopes live on the AppConfig (`access_areas`, `access_token_scopes`,
  `access_route_rules`), every admin view carries `access_area`; a new admin route without one fails
  `tests/test_access_ownership.py`.
- Default: do not commit — git is the user's call.
- No AI attribution in commits or PR descriptions.

## Architecture

```
src/django_accounts/
├── models/                         # ORM models + the UserExtensionProxy proxy
│   ├── customer.py                 #   Customer (O2O → User), UserExtensionProxy
│   ├── address.py                  #   Address (FK → Customer), AddressManager
│   ├── channel.py                  #   Channel (idx, label, language FK)
│   ├── file.py                     #   File, AddressFile (both FK → Customer)
│   ├── group.py                    #   Group (customer segmentation)
│   ├── wishlist.py                 #   Wishlist, WishlistProduct (M2M through)
│   ├── product_representation.py   #   ProductRepresentation (SKU + name_t9n per channel)
│   ├── revoke.py                   #   Revoke (logout tracking)
│   ├── socials.py                  #   SocialLoginProviders (google/facebook config)
│   ├── apiadminkey.py              #   APIAdminKey (SHA256 generated, per channel)
│   └── managers.py                 #   WishlistManager (get_record, guest_wishlist_to_customer)
│
├── views/
│   ├── api/                        # Public v1 function-based views
│   │   ├── customer.py             #   signup, confirm, me, profile, delete, password
│   │   ├── token.py                #   create, refresh, blacklist, validate
│   │   ├── address_book.py         #   addresses CRUD + defaults + file upload
│   │   ├── wishlist.py             #   wishlist detail + product add/remove/extra
│   │   └── social_login.py         #   Google/Facebook OAuth2 login + callback + tokenize
│   └── admin/
│       └── customer.py             #   admin_customer_delete (by email, @admin_view)
│
├── api/                            # DRF v2 admin API (read-only)
│   └── admin/
│       ├── views.py                #   CustomerViewSet, GroupViewSet, ChannelViewSet
│       ├── urls.py                 #   endpoints under api/accounts/v2/admin/
│       └── pagination.py           #   AdminPageNumberPagination (20/page, max 100)
│
├── schemas/                        # Pydantic v2 response schemas (v2 admin API)
├── services/                       # CustomerService, admin query service, CSV import helpers
├── dto/                            # marshmallow-dataclass request/response objects (v1 API)
├── management/commands/            # management commands (kebab-case filenames)
├── utils/                          # decorators (channel_view, admin_view), address helpers
├── backends.py                     # Custom auth backend
├── email_confirmation.py           # EmailChangePasswordHMAC (password reset HMAC)
├── password_validators.py          # CapitalSymbolAndNumbersValidator, SpaceValidator
├── jwt.py                          # TokenAccessSocialLogin (short-lived social token)
├── settings.py                     # module settings (see docs/configuration.md)
└── urls.py                         # URL routing (public + admin prefix from settings)
```

Layer rule: `Views → Services → Models → DB`. No ORM in views — use services or managers.

Auth: v1 views use `@authenticate` + `@require_authentication` (simplejwt Bearer), `@channel_view` (resolves the
`Channel` from `channel_idx`) and `@admin_view` (`X-API-ADMIN-KEY` through `utils/api_keys.py` `key_is_valid`: an
access token of scope `accounts.erase` with `django_access` installed, else an `APIAdminKey` row). The v2 admin API
uses `JWTAuthentication` + `IsAdminUser`.

| Topic | Where |
|---|---|
| Overview, key concepts, authentication flow | `docs/index.md` |
| v1 and v2 endpoints, auth mechanisms | `docs/api.md` |
| Entities, key enums, unique constraints | `docs/data-model.md` |
| Settings reference, JWT, password policy, social login | `docs/configuration.md` |
| Management commands | `docs/commands.md` |
| Testing, the run without `django_access` | `docs/testing.md` |
| ERD config (groups customers-identity, wishlist-commerce) and generated diagrams | `docs/erd-config.yaml`, `docs/erd.md` |

## Settings

The ten most used; full reference in `docs/configuration.md`.

| Setting | Default | Description |
|---------|---------|-------------|
| `JWT_SECRET` | **required** | Secret for the short-lived social login token |
| `PRIVATE_DIR` | **required** | Root for private file storage |
| `MIGRATION_0023_MECHANISM` | **required** | Wishlist migration mode: 1=delete all, 2=multi-channel, 3=assign |
| `EMAIL_DOUBLE_OPTIN` | `True` | Send confirmation email on signup |
| `IS_ACTIVE_REQUIRED` | `True` | Block login if customer.is_active=False |
| `IS_VERIFY_REQUIRED` | `False` | Block login if customer.is_verified=False |
| `ACCOUNTS_PASSWORD_MIN_LENGTH` | `8` | Minimum password length |
| `API_PUBLIC_BASE_URL` | `"api"` | Public URL prefix |
| `API_ADMIN_BASE_URL` | `"api-admin"` | Admin URL prefix |
| `T9N_DEFAULT_LANG` | `"pl"` | Fallback language for name_t9n resolution |

`AUTHENTICATION_BACKENDS` must list `django_accounts.backends.JWTAccessBackend` before `ModelBackend`
(nothing checks it at boot; see Gotchas).

## Gotchas

- v1 customer views use `@authenticate` → `django.contrib.auth.authenticate(request)`, which only tries `AUTHENTICATION_BACKENDS`. Without `JWTAccessBackend` registered the Bearer token is never read and every customer endpoint is 401
- `customer/tokens/` for a valid login without a `Customer` (staff-only user) is 403 `user_not_customer`
- `customer/tokens/` is the CMS staff login: with `django_access` installed it runs access' failed-login guard
  (`django_access.services.login_guard`, the counters of the service's `api/token/`; settings
  `AUTH_TOKEN_*`) — 429 + `Retry-After` before the password check; without access no limit
- With `django_access` installed, `receivers.create_staff_customer` (connected in `AccountsConfig.ready()`) gives an
  account from `staff_user_created` its `Customer` + verified `EmailAddress`; it runs in the access transaction — a
  raise rolls the account back
- `JWT_SECRET`, `PRIVATE_DIR` and `MIGRATION_0023_MECHANISM` raise `OSError` at import if unset — set all three before starting Django
- `T9N_DEFAULT_LANG` defaults to `"pl"` not `"en"` — affects `ProductRepresentation.name` and `name_lang()` fallback
- `Customer.email` is a `@property` querying allauth `EmailAddress` — always access via `customer.email.email`, not a plain field
- `UserExtensionProxy` is a proxy model on Django's User — excluded from ERD, exposes only `is_customer` property
- v1 views use marshmallow DTOs (legacy pattern). v2 admin API uses Pydantic + drf-spectacular
- `File` is stored in `FileSystemStorage` under `PRIVATE_DIR/customer/{uid}/` — not in STATIC/MEDIA, requires custom download view
- `AddressFile.save()` auto-sets `customer` from `address.customer` and overrides `file_type` to `ADDRESS_ATTACHMENT`
- Social login produces a short-lived `access_social` token — frontend exchanges it at `customer/tokenize/` for simplejwt tokens
- `django_accounts.Channel` is separate from `django_pim.Channel` — sync via `fill-accounts-product-representation-from-pim`
- One `Wishlist` per `(customer, channel)` — `MIGRATION_0023_MECHANISM` controls how pre-existing data was restructured
