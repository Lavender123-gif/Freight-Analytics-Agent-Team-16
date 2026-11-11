"""Anthropic client construction and model-call settings (task 09).

The API key is read from the environment or from the git-ignored `.env` at the repo root. It is never logged,
printed or written anywhere. Model name, thinking mode, effort and caching come from `config/model.yaml`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import anthropic
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_CONFIG = ROOT / "config" / "model.yaml"


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if "ANTHROPIC_API_KEY" in os.environ or not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@lru_cache(maxsize=1)
def model_settings() -> dict:
    return yaml.safe_load(MODEL_CONFIG.read_text())


def client() -> anthropic.Anthropic:
    _load_dotenv()
    s = model_settings()
    return anthropic.Anthropic(max_retries=s.get("sdk_max_retries", 4), timeout=s.get("timeout_s", 120))


def request_kwargs() -> dict:
    """Model-level request fields shared by every call: model, max_tokens, thinking, effort."""
    s = model_settings()
    kw: dict = {"model": s["model"], "max_tokens": s["max_tokens"]}
    if s.get("thinking") == "off":
        # Sonnet 5.5: {"type": "disabled"} is a 400; "between_tools" is the thinking-off setting (effort <= high).
        kw["thinking"] = {"type": "between_tools"}
    elif s.get("thinking") == "adaptive":
        kw["thinking"] = {"type": "adaptive"}
    if s.get("effort"):
        kw["output_config"] = {"effort": s["effort"]}
    return kw
