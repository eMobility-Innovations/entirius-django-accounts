---
title: "Accounts: Database Diagrams"
description: "Auto-generated ER diagrams for the Accounts module."
sidebar:
  badge:
    text: "Auto-gen"
    variant: "note"
---

:::caution[Auto-generated]
These diagrams are auto-generated from Django model introspection.
Do not edit. Run `make erd` in entirius-docker to regenerate.
:::

## Customers & Identity

```d2 layout=elk
Customer: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  user_id: int {constraint: foreign_key}
  uid: uuid {constraint: unique}
  language_id: int {constraint: foreign_key}
  shipping_address_id: int {constraint: foreign_key}
  billing_address_id: int {constraint: foreign_key}
  last_session_country_id: int {constraint: foreign_key}
  group_id: int {constraint: foreign_key}
  source_channel_id: int {constraint: foreign_key}
}

Address: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  customer_id: int {constraint: foreign_key}
  firstname: varchar
  lastname: varchar
  street: varchar
  city: varchar
  postcode: varchar
  telephone: varchar
}

File: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  customer_id: int {constraint: foreign_key}
  file_type: varchar
  upload: varchar
  name: text
  "label": varchar
}

AddressFile: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  customer_id: int {constraint: foreign_key}
  file_ptr_id: int {constraint: primary_key}
  address_id: int {constraint: foreign_key}
  file_type: varchar
  upload: varchar
  name: text
  "label": varchar
}

Group: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  code: varchar {constraint: unique}
  name: varchar {constraint: unique}
  is_active: bool
}

Channel: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  idx: varchar {constraint: unique}
  "label": varchar {constraint: unique}
  language_id: int {constraint: foreign_key}
}

Revoke: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  user_id: int {constraint: foreign_key}
}

Country: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Country (External: django_regional)"
}

Language: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Language (External: django_regional)"
}

User: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "User (External: auth)"
}



Customer.user_id -> User.id: {style.stroke: "#484B57"}

Customer.language_id -> Language.id: {style.stroke: "#484B57"}

Customer.shipping_address_id -> Address.id: {style.stroke: "#00ACC1"}

Customer.billing_address_id -> Address.id: {style.stroke: "#00ACC1"}

Customer.last_session_country_id -> Country.id: {style.stroke: "#484B57"}

Customer.group_id -> Group.id: {style.stroke: "#00ACC1"}

Customer.source_channel_id -> Channel.id: {style.stroke: "#00ACC1"}

Customer.id <-> Channel.id: {style.stroke: "#00ACC1"}

Address.customer_id -> Customer.id: {style.stroke: "#00ACC1"}

File.customer_id -> Customer.id: {style.stroke: "#00ACC1"}

AddressFile.customer_id -> Customer.id: {style.stroke: "#00ACC1"}

AddressFile.file_ptr_id -> File.id: {style.stroke: "#00ACC1"}

AddressFile.address_id -> Address.id: {style.stroke: "#00ACC1"}

Channel.language_id -> Language.id: {style.stroke: "#484B57"}

Revoke.user_id -> User.id: {style.stroke: "#484B57"}
```

## Wishlist & Commerce

```d2 layout=elk
Wishlist: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  channel_id: int {constraint: foreign_key}
  customer_id: int {constraint: foreign_key}
  uid: uuid
}

WishlistProduct: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  wishlist_id: int {constraint: foreign_key}
  product_id: int {constraint: foreign_key}
  is_external: bool
  sources: jsonb
  extra: jsonb
}

ProductRepresentation: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  channel_id: int {constraint: foreign_key}
  sku: varchar
  name_t9n: jsonb
}

APIAdminKey: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  channel_id: int {constraint: foreign_key}
  key: varchar
}

SocialLoginProviders: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  channel_id: int {constraint: foreign_key}
  is_enabled: bool
  provider: varchar
  name: varchar
  client_id: varchar
  key: varchar
  callback_url: varchar
}

Channel: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Channel (See customers-identity diagram)"
}

Customer: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Customer (See customers-identity diagram)"
}



Wishlist.channel_id -> Channel.id: {style.stroke: "#484B57"}

Wishlist.customer_id -> Customer.id: {style.stroke: "#484B57"}

WishlistProduct.wishlist_id -> Wishlist.id: {style.stroke: "#00ACC1"}

WishlistProduct.product_id -> ProductRepresentation.id: {style.stroke: "#00ACC1"}

ProductRepresentation.channel_id -> Channel.id: {style.stroke: "#484B57"}

APIAdminKey.channel_id -> Channel.id: {style.stroke: "#484B57"}

SocialLoginProviders.channel_id -> Channel.id: {style.stroke: "#484B57"}
```
