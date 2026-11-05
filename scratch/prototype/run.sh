#!/bin/sh
# Run a prototype script with its extra dependencies in an ephemeral uv environment (pyproject.toml untouched).
# Usage from repo root: sh scratch/prototype/run.sh run_dev.py
cd "$(dirname "$0")/../.." || exit 1
exec uv run --with pydantic --with pyyaml --with presidio-analyzer \
  --with "en_core_web_lg @ https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl" \
  python "scratch/prototype/$1"
