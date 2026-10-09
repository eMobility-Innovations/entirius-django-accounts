---
title: "Management Commands"
description: "CLI commands for importing accounts, generating API keys, and data migration."
---

Run all commands with `python manage.py <command>` from the Volkanos service root.

## accounts-import-from-csv

Creates `User`, `EmailAddress`, and `Customer` records from a CSV file.

```bash
python manage.py accounts-import-from-csv
python manage.py accounts-import-from-csv --file_path /data/import/accounts/accounts.csv
```

**Default path:** `{IMPORT_DIR}/accounts/accounts.csv`

**CSV requirements:**

- Minimum required column: `email`
- All created accounts have `is_verified=True` and `is_active=True` (unless specified in CSV)
- Passwords are randomly generated (20 characters)
- JSON fields in the CSV use `|` as the string delimiter instead of `"` to avoid quoting conflicts

**Optional CSV columns:** `first_name`, `last_name`, `external_id`, `extra` (JSON), `group` (group name)

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--file_path` | No | Path to CSV file. Defaults to `{IMPORT_DIR}/accounts/accounts.csv` |

## addresses-import-from-csv

Creates `Address` records from a CSV file and links them to existing customers.

```bash
# Look up customers by email (default)
python manage.py addresses-import-from-csv --by_email

# Look up customers by external_id
python manage.py addresses-import-from-csv --by_external_id

# With explicit file path
python manage.py addresses-import-from-csv --by_email --file_path /data/import/accounts/addresses.csv
```

**Default path:** `{IMPORT_DIR}/accounts/addresses.csv`

**CSV requirements:**

- Minimum required column: `email` or `external_id` (depending on lookup mode)
- For personal addresses (`is_company=False`): provide `first_name` and `last_name`
- For company addresses (`is_company=True`): provide `company` and `tax_id`. Providing `tax_id` automatically sets `is_company=True`
- `address_id` is optional

**Assign as default address:** use the `assign` column:

| Value | Effect |
|-------|--------|
| `1` | Set as default billing address |
| `2` | Set as default shipping address |
| `3` | Set as default billing and shipping address |

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--file_path` | No | Path to CSV file. Defaults to `{IMPORT_DIR}/accounts/addresses.csv` |
| `--by_email` | No | Look up customer by email (default behavior) |
| `--by_external_id` | No | Look up customer by `external_id` instead of email |

## fill-accounts-product-representation-from-pim

Populates `ProductRepresentation` records by pulling product data from PIM for a given shop.

```bash
python manage.py fill-accounts-product-representation-from-pim --pim_shop_idx test_channel_pl
```

Run this after initial PIM data is imported to sync product representations used by the accounts module (wishlists, order history display).

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--pim_shop_idx` | Yes | PIM shop/channel identifier to pull products from |

## generate-api-admin-key

Generates a new `APIAdminKey` for a channel and saves it to a file.

```bash
python manage.py generate-api-admin-key my_channel_idx
python manage.py generate-api-admin-key my_channel_idx --file_path /secrets/accounts-admin.key
```

The key is printed to stdout and written to the file. Use the generated key in integration services (ERP, B2B portals) that need admin-level access to the accounts API without a user session.

**Default file path:** `{DATA_DIR}/tmp/accounts-api-admin-key/key`

With `django_access` installed the command refuses: keys are access tokens there — issue one with
`manage.py access_token create --scope accounts.erase --channel <idx> --expires-days <n> --application <name>`.

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `channel_idx` | Yes | The `idx` of the Channel to generate the key for |
| `--file_path` | No | Path where the key is saved. Defaults to `{DATA_DIR}/tmp/accounts-api-admin-key/key` |

## module-accounts-export-to-magento

Exports customer accounts to Magento 2 via its REST API.

```bash
python manage.py module-accounts-export-to-magento
```

Requires `MAGENTO2_URL_FOR_CHECKOUT_EXPORT` and `MAGENTO2_TOKEN_FOR_CHECKOUT_EXPORT` to be set in settings. See [Configuration](./configuration/) for details.

This command lives in the separate `entirius-django-accounts-export-to-magento-api` module. Install that module to use it.

## Command Summary

| Command | Description |
|---------|-------------|
| `accounts-import-from-csv` | Import customer accounts from CSV file (`--file_path`, defaults to `IMPORT_DIR/accounts/accounts.csv`) |
| `addresses-import-from-csv` | Import customer addresses from CSV file |
| `fill-accounts-product-representation-from-pim` | Sync ProductRepresentation cache from PIM data (`--pim_shop_idx`; requires the `pim` extra) |
| `generate-api-admin-key` | Generate SHA256 APIAdminKey for a channel and save to file (`channel_idx`, `--file_path`); refuses when django-access is installed |
| `module-accounts-export-to-magento` | Export accounts to Magento2 (empty command stub) |
