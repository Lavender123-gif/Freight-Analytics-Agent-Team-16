"""Load the configuration files once. Thresholds and rules live in config/*.yaml, never in code."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DEV_PATH = ROOT / "data" / "processed" / "dev.csv"
RUNS_DIR = ROOT / "data" / "interim" / "runs"          # git-ignored; every row-level output goes here
SKILL_PATH = ROOT / "skill" / "freight-dispute-line-items" / "SKILL.md"
EXAMPLES_PATH = ROOT / "data" / "interim" / "skill" / "examples.json"      # real dev rows, redacted, git-ignored
# tracked fallback (pending P-06, decided): newly written synthetic examples, used only when the file above is absent
SYNTHETIC_EXAMPLES_PATH = SKILL_PATH.parent / "examples" / "synthetic_examples.json"


PROTECTED_READS = (ROOT / "data" / "processed" / ("test" + ".csv"), ROOT / "data" / ("raw"))


class ProtectedPathError(PermissionError):
    """Raised when code tries to read the test split or the raw Excel without the owner's explicit switch."""


def assert_readable(path: Path | str) -> Path:
    """Hard check at the read layer (pending P-18, audit L6): refuse the test split and anything under the raw-data
    folder, however the path was built (relative, symlinked, '..'). The deny rules in .claude/settings.json only
    match command text; this check runs on the resolved path. The owner opens the gate for one process with
    FL_ALLOW_TEST_SPLIT=1 (final test, V4) or FL_ALLOW_RAW=1 (re-making the split). Returns the resolved path."""
    import os
    rp = Path(path).expanduser().resolve()
    test_split, raw_dir = (x.resolve() for x in PROTECTED_READS)
    if rp == test_split and os.environ.get("FL_ALLOW_TEST_SPLIT") != "1":
        raise ProtectedPathError("the test split is not readable during development (set FL_ALLOW_TEST_SPLIT=1; owner only)")
    if (rp == raw_dir or raw_dir in rp.parents) and os.environ.get("FL_ALLOW_RAW") != "1":
        raise ProtectedPathError("the raw Excel is not readable here (set FL_ALLOW_RAW=1; owner only)")
    return rp


def _load(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())


RULES = _load("rules.yaml")
TAXONOMY = _load("taxonomy.yaml")
TAX = _load("tax_rules.yaml")
CODES: dict = TAXONOMY["codes"]

CANADIAN = set(TAX["provinces"])
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
                "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split())


def country(state: str | None) -> str:
    """Country from a two-letter province/state code (decision 4.3: the US/CAN column is not trusted)."""
    if not state:
        return "UNKNOWN"
    if state in CANADIAN:
        return "CA"
    if state in US_STATES:
        return "US"
    return "OTHER"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def examples_file() -> tuple[Path | None, str]:
    """Which worked-example library a run uses: (path, source). The real redacted dev examples when that git-ignored
    file exists ('dev_redacted'); otherwise the synthetic examples shipped in the skill folder ('synthetic');
    (None, 'missing') when neither exists."""
    if EXAMPLES_PATH.exists():
        return EXAMPLES_PATH, "dev_redacted"
    if SYNTHETIC_EXAMPLES_PATH.exists():
        return SYNTHETIC_EXAMPLES_PATH, "synthetic"
    return None, "missing"


def versions() -> dict[str, str]:
    ex_path, ex_source = examples_file()
    return {
        "rules": RULES["version"],
        "taxonomy": TAXONOMY["version"],
        "tax": TAX["version"],
        "skill_sha": file_sha(SKILL_PATH) if SKILL_PATH.exists() else "missing",
        # task 19: the whole skill folder (core and topic references) and the layout
        "skill_folder_sha": _folder_sha(SKILL_PATH.parent),
        "skill_layout": _skill_layout(),
        "screen_skill_sha": file_sha(SKILL_PATH.parents[1] / "screening-for-instructions" / "SKILL.md")
        if (SKILL_PATH.parents[1] / "screening-for-instructions" / "SKILL.md").exists() else "missing",
        # audit L4: the example library and the full system prompt (SKILL.md + taxonomy + examples) are versioned too
        "examples_sha": file_sha(ex_path) if ex_path is not None else "missing",
        "examples_source": ex_source,          # dev_redacted | synthetic | missing
        "taxonomy_layout": _layout(),          # task 14 stage 2: internal | client_rooted
    }


def _folder_sha(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix in (".md", ".json"):
            h.update(str(p.relative_to(folder)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:12]


def _skill_layout() -> str:
    from freight_lineitems.skilltext import layout
    return layout()


def _layout() -> str:
    from freight_lineitems.tools import taxonomy_layout
    return taxonomy_layout()


def category(code: str) -> str:
    return CODES[code]["category"] if code in CODES else "UNKNOWN"
