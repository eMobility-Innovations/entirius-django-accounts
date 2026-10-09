---
title: "API"
description: "v1 public and admin endpoints, their auth mechanisms, and the read-only v2 admin API."
---

## API v1 Endpoints

Function-based views (v1 style: marshmallow DTO validation). URL prefix configured via
`API_PUBLIC_BASE_URL` and `API_ADMIN_BASE_URL` settings (defaults: `api`, `api-admin`).

```
{PUBLIC_BASE_URL}/accounts/<version>/<channel_idx>/
├── customer/tokens/                POST (create)          -- JWT login (staff too: the CMS); failed logins limited with access
├── customer/tokens/refresh/        POST                   -- refresh access token
├── customer/tokens/blacklist/      POST (auth)            -- logout / invalidate refresh
├── customer/tokens/validate/       POST                   -- validate access token
├── customer/signup/                POST                   -- register + double optin email
├── customer/signup/<uid>/          POST                   -- confirm email (key via querystring)
├── customer/password/reset/        POST                   -- send password reset email
├── customer/password/reset/<key>/  POST                   -- confirm reset with new password
├── customer/password/change/       POST (auth)            -- change password (old + new)
├── customer/me/                    GET (auth)             -- authenticated user info
├── customer/<uid>/profile/         GET, PATCH (auth)      -- customer profile
├── customer/<uid>/delete/          DELETE (auth)          -- self-delete + blacklist tokens
├── customer/login/<provider>/      GET                    -- social OAuth2 redirect
├── customer/login/<provider>/callback/ GET               -- social OAuth2 callback
├── customer/tokenize/              GET                    -- exchange access_social token
├── customer/<uid>/addresses/       GET, PUT, PATCH, DELETE (auth) -- address CRUD (?id=pk)
├── customer/<uid>/addresses/defaults/ GET, POST (auth)   -- get/set billing+shipping defaults
├── customer/<uid>/addresses/files/ GET, POST             -- upload / download address files
├── wishlist/                       GET, POST (auth/guest) -- wishlist detail + merge guest→customer
└── wishlist/product/               POST, DELETE, PATCH   -- add/remove/update extra on products

{ADMIN_BASE_URL}/accounts/<version>/<channel_idx>/
└── customer/delete                 DELETE (@admin_view)   -- admin delete customer by email
```

**Auth mechanisms (v1):**
- `@authenticate` + `@require_authentication` — simplejwt Bearer token
- `@admin_view` — X-API-ADMIN-KEY authentication (admin endpoints) through `utils/api_keys.py` `key_is_valid`: with
  `django_access` installed an access token of scope `accounts.erase` (`verify_api_key`, the `APIAdminKey` table is never
  read), else the `APIAdminKey` row (soft dependency — never in `pyproject.toml`); a pinned token erases only
  customers of its channel (`erase_channel`, `Customer.source_channel`), an unpinned one in every channel
- `@channel_view` — resolves `Channel` from URL `channel_idx` into `kwargs["channel"]`

## API v2 Admin (Read-Only)

URL prefix: `api/accounts/v2/admin/` — no channel scope (admin sees cross-channel data).
Auth: `JWTAuthentication` + `IsAdminUser`. Pydantic response schemas + drf-spectacular OpenAPI.

```
api/accounts/v2/admin/
├── customers/              GET    -- paginated list (search, group, channel, status filters, ordering)
├── customers/<uid>/        GET    -- full profile + addresses + session info + wishlist count
├── groups/                 GET    -- customer groups with customer counts
└── channels/               GET    -- accounts channels with default language
```
