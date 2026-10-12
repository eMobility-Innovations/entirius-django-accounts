---
title: "Testing"
description: "Accounts test suite: PostgreSQL requirement and the run without django_access."
---

Tests run on postgres via `DATABASE_URL` (CI provides a postgres service; locally point it at any postgres 15+).

```bash
make install
make test
```

`make test-legacy` runs the same suite with `ENTIRIUS_TEST_NO_ACCESS=1`: `django_access` stays out of
`INSTALLED_APPS` even when it is importable, so the admin key is checked against the `APIAdminKey` table (the path
of an installation without access).
