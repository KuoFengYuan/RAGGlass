#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check backend scripts tests
.venv/bin/ruff format --check backend scripts tests
.venv/bin/pytest -q -m 'not integration'
npm --prefix frontend run format:check
npm --prefix frontend run build
node --check scripts/capture_ui_docs.mjs
.venv/bin/python scripts/check_docs.py
