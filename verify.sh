#!/usr/bin/env bash
# The suite gate: the command REPO-CONTRACT.toml [tests] names and the gate runner executes.
# The suite owns its datastore: each run gets its own database name, so two concurrent runs
# on one runner never share (pytest-django creates test_<name> and drops it at the end).
set -euo pipefail
cd "$(dirname "$0")"
role="entirius_accounts_test"
db="eda_$(date +%s)_$$"
: "${DATABASE_URL:=postgresql://${role}:${role}@127.0.0.1:5432/${db}}"
export DATABASE_URL
uv sync --all-extras --frozen --quiet
uv run --no-sync pytest -q
