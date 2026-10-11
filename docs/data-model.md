---
title: "Data Model"
description: "Entities and relations, key enums and unique constraints of the Accounts module."
---

## Entities

```
User (Django auth)
    └── Customer (O2O)               -- profile, is_active, is_verified, uid
         ├── source_channel: Channel  -- registration channel
         ├── blacklist_channels: [Channel]  -- M2M, no-login list
         ├── group: Group             -- customer segment
         ├── language: Language       -- from django_regional
         ├── billing_address: Address  (FK, nullable)
         ├── shipping_address: Address (FK, nullable)
         └── addresses: [Address]     -- all addresses (reverse FK)
              └── AddressFile          -- file attachments (FK → Address + Customer)
                    └── File           -- base file model (stored in PRIVATE_DIR/customer/{uid}/)

Channel
    ├── customers_source: [Customer]   -- reverse: customers registered here
    ├── customers_blacklist: [Customer] -- reverse: blocked customers
    ├── Wishlist                        -- per channel
    ├── ProductRepresentation           -- SKU name cache per channel
    ├── SocialLoginProviders            -- OAuth provider config per channel
    └── APIAdminKey                     -- admin API auth key per channel

Wishlist (uid, customer FK, channel FK)
    └── WishlistProduct (through table)
         └── ProductRepresentation (sku + name_t9n JSON)

Revoke (user FK, created_at)           -- tracks last logout time

UserExtensionProxy                     -- proxy on User, adds is_customer property
```

- `Customer.email` is a `@property` — queries allauth `EmailAddress` (primary + verified)
- `Customer.first_name` / `Customer.last_name` delegate to `user.first_name` / `user.last_name`
- `ProductRepresentation.name` falls back to `sku` if `name_t9n` is empty

## Key Enums

| Enum | Values |
|------|--------|
| **Sex** (Customer) | male, female, other (TextChoices) |
| **FileType** | default, address_attachment (TextChoices) |
| **AddressSourceEnum** | UNKNOWN(0), PWA(1), MAGENTO(2), EXTERNAL(3), CSV(4) |
| **SocialLoginProviders.provider** | google, facebook (hard-coded choices) |

## Unique Constraints

| Model | Field(s) | Type |
|-------|----------|------|
| Customer | `uid` | unique (UUID) |
| Channel | `idx` | unique |
| Channel | `label` | unique |
| Group | `code` | unique |
| Group | `name` | unique |
| ProductRepresentation | `(sku, channel)` | UniqueConstraint |
| Wishlist | `(customer, channel)` | UniqueConstraint |
| Address | check: `(firstname+lastname) OR company NOT NULL` | CheckConstraint |
| Address | check: `is_company → company+tax_id NOT NULL` | CheckConstraint |
