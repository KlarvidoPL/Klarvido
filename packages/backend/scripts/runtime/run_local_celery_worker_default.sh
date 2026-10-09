#!/bin/bash

set -e

# Sync once before watching source. Dependency installation writes Python files
# into .venv and must not trigger another worker restart.
uv sync --frozen

exec uv run --no-sync watchmedo auto-restart \
  --directory=/app/apps \
  --directory=/app/common \
  --directory=/app/config \
  --pattern=*.py \
  --recursive \
  -- uv run --no-sync celery -A config worker -l info
