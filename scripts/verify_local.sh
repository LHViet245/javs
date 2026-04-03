#!/usr/bin/env bash
set -euo pipefail

./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
