#!/bin/sh
# Regenerate (or with --check, only verify) docs/status/project_status.{zh,en}.md from
# docs/status/cards.yaml. Ephemeral uv environment; pyproject.toml untouched.
# Usage from repo root: sh scratch/status/run.sh [--check]
cd "$(dirname "$0")/../.." || exit 1
exec uv run --no-project --with pyyaml --with jinja2 python scratch/status/build_status.py "$@"
