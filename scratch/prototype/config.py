"""Load the prototype's configuration files once. Thresholds and rules live in YAML, not in code."""

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEV_PATH = ROOT / "data" / "processed" / "dev.csv"
OUT_DIR = ROOT / "data" / "interim" / "prototype"   # git-ignored; row-level outputs go here only

RULES = yaml.safe_load((HERE / "rules.yaml").read_text())
CATALOG = yaml.safe_load((HERE / "diagnostics_catalog.yaml").read_text())
TAXONOMY = yaml.safe_load((HERE / "taxonomy.yaml").read_text())
TAX = yaml.safe_load((HERE / "tax_rules.yaml").read_text())

CANADIAN = set(TAX["provinces"])
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
                "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC PR".split())

VERSIONS = {
    "rules": RULES["version"], "catalog": CATALOG["version"], "taxonomy": TAXONOMY["version"], "tax": TAX["version"],
}


def country(state: str | None) -> str:
    if not state:
        return "unknown"
    if state in CANADIAN:
        return "CA"
    if state in US_STATES:
        return "US"
    return "other"
