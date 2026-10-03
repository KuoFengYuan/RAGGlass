#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check backend scripts tests
.venv/bin/ruff format --check backend scripts tests
.venv/bin/pytest -q -m 'not integration'
npm --prefix frontend run format:check
npm --prefix frontend run build
for script in scripts/*.mjs; do
  node --check "$script"
done
node --test tests/test_public_capture.mjs
.venv/bin/python scripts/check_docs.py
