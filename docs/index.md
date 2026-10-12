---
title: "Accounts"
description: "Authentication, user profiles, addresses, and permissions."
sidebar:
  label: "Overview"
  collapsed: true
---

Accounts (`django-accounts`) handles the full customer identity layer: registration, login, JWT auth, password management, address book, wishlists, consent management, and channel-scoped access control.

## Key Concepts

- **User** — Django auth user extended by `django-accounts`. Email is the primary identifier; emails are normalized to lowercase.
- **Customer** — One-to-one with User. Holds ecommerce-specific data: `external_id`, `extra` JSON, channel assignment, and file attachments.
- **Channel** — Sales channel scope. Accounts and wishlists are channel-scoped.
- **Group** — Permission grouping for customers. Assigned during signup or import.
- **Address** — Billing and shipping addresses linked to Customer. Supports `is_company`, `tax_id`, `external_id`, and assignment flags (billing/shipping/both).
- **Wishlist** — Per-channel product list. Guest wishlists can be merged into a logged-in customer account.
- **ConsentType / Consent** — GDPR marketing consent types and per-customer consent records.
- **APIAdminKey** — Channel-scoped API key for admin-level integrations (B2B, ERP sync).

## Features

| Feature | Description |
|---------|-------------|
| JWT authentication | Access + refresh token pair via `djangorestframework-simplejwt` |
| Double opt-in | Email verification on registration (configurable) |
| Social login | Google and Facebook OAuth2 via `django-allauth` |
| Password policy | Configurable minimum length, capitals, digits, special characters |
| Address book | Multiple billing/shipping addresses per customer |
| Wishlist | Per-channel saved products, guest-to-logged merge |
| Consent management | GDPR-compliant consent types and per-user records |
| Channel blacklist | Restrict cross-channel account access |
| Private file storage | Customer file attachments stored outside web root |
| Magento export | Export accounts to Magento 2 (via separate submodule) |

## Authentication Flow

```
POST /api/accounts/v1/{channel}/customer/login/
  → returns { access, refresh }

POST /api/accounts/v1/{channel}/customer/token/refresh/
  → rotates refresh token, returns new access

POST /api/accounts/v1/{channel}/customer/logout/
  → blacklists refresh token
```

Authentication backend order matters. The module registers `JWTAccessBackend` first, then falls back to Django's `ModelBackend` (required for `/admin`):

```python
AUTHENTICATION_BACKENDS = [
    "django_accounts.backends.JWTAccessBackend",
    "django.contrib.auth.backends.ModelBackend",
]
```

## Related Modules

- **[Accounts Keycloak](./accounts-keycloak/)** — Keycloak SSO integration using OAuth2 PKCE flow
- **[Database Diagrams](./erd/)** — auto-generated ER diagrams for all Accounts models

## API

### v1 (Public)

Customer-facing endpoints under `/api/accounts/v1/{channel}/` for registration, login, profile, addresses, and wishlists. Legacy admin endpoint at `/api-admin/accounts/v1/{channel}/customer/delete` (GDPR erase by e-mail): with `django_access` a channel-pinned `accounts.erase` token deletes only customers registered in that channel (`source_channel`); an unpinned token, or the legacy key without `django_access`, deletes in every channel.

### v2 Admin (Read-Only)

Admin endpoints under `/api/accounts/v2/admin/`. JWT + `IsAdminUser` required. No channel scope — admin sees cross-channel data.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `customers/` | GET | Paginated list with search, group/channel/status filters, ordering |
| `customers/{uid}/` | GET | Full profile with addresses, session info, wishlist count |
| `groups/` | GET | Customer groups with customer counts |
| `channels/` | GET | Accounts channels with default language |

Pydantic response schemas, `@extend_schema` OpenAPI docs. See the [API Reference](/api/cms/) for interactive explorer.
