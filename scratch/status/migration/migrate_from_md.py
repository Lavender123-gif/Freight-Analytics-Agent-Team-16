"""One-off migration (task 04): legacy hand-written boards -> docs/status/cards.yaml.

Not part of the regular workflow. After task 04, cards.yaml is the single source and is
edited directly; this script is kept only as a record of how the content was migrated.

Inputs
  data/interim/status_legacy/project_status.{zh,en}.md   copies of the task-03 boards (git-ignored)
  scratch/status/migration/overlay_task04.yaml           fields added in task 04 (colour, evidence,
                                                          summary, thresholds, B04 dependency, links)
Output
  docs/status/cards.yaml

The legacy text of every card item (lead sentence and bullets) is copied verbatim. The only
deliberate rewrite is "变绿需要" -> "变浅绿需要" / "to turn green" -> "to turn light green",
because the old "green" corresponds to the new "light green".

Run from the repo root:
  uv run --offline --no-project --with pyyaml python scratch/status/migration/migrate_from_md.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "data/interim/status_legacy"
OVERLAY = Path(__file__).with_name("overlay_task04.yaml")
OUT = ROOT / "docs/status/cards.yaml"
HEADER = Path(__file__).with_name("cards_header.txt")

ITEM_KEYS = ["what_is", "status_detail", "deliverable_note", "start_conditions",
             "approach", "depends", "open_items", "completion_text"]
RENAMES = {"zh": [("变绿需要", "变浅绿需要")], "en": [("to turn green", "to turn light green")]}

CARD_RE = re.compile(r"^### (\S+) (.+?)\s*(🟩|🟨|🟥|⬜)\s*$")
ITEM_RE = re.compile(r"^(\d)\. \*\*(.+?)\*\*(.*)$")
BULLET_RE = re.compile(r"^   - (.*)$")
COLUMN_RE = re.compile(r"^## ([A-Z]) (.+)$")
ROW_RE = re.compile(r"^\| (\w+) \| (.+?) \| (🟩|🟨|🟥|⬜) \| (.+) \|$")


def clean_lead(rest: str) -> str:
    """Text after '**label**': strip the leading colon (zh '：' or en ': ').

    A parenthesised note such as "（已完成，记录做法）：..." / "(done, recorded): ..." is kept
    verbatim together with its colon.
    """
    return re.sub(r"^(：|:)\s*", "", rest.strip())


def rename(text: str, lang: str) -> str:
    for old, new in RENAMES[lang]:
        text = text.replace(old, new)
    return text


def parse(lang: str) -> tuple[dict, dict, dict]:
    lines = (LEGACY / f"project_status.{lang}.md").read_text(encoding="utf-8").splitlines()
    cards: dict[str, dict] = {}
    rows: dict[str, dict] = {}
    columns: dict[str, str] = {}
    cur = None
    item = None
    for line in lines:
        if m := ROW_RE.match(line):
            if m.group(1) not in ("编号", "ID"):
                rows[m.group(1)] = {"name": m.group(2), "status_line": m.group(4)}
            continue
        if m := COLUMN_RE.match(line):
            columns[m.group(1)] = m.group(2)
            continue
        if m := CARD_RE.match(line):
            cur = {"name": m.group(2), "items": {}, "free": []}
            cards[m.group(1)] = cur
            item = None
            continue
        if cur is None or line.startswith("---") or line.startswith("## "):
            if line.startswith("## "):
                cur = None
            continue
        if m := ITEM_RE.match(line):
            key = ITEM_KEYS[int(m.group(1)) - 1]
            item = {"lead": rename(clean_lead(m.group(3)), lang), "bullets": []}
            cur["items"][key] = item
            continue
        if (m := BULLET_RE.match(line)) and item is not None:
            item["bullets"].append(rename(m.group(1), lang))
            continue
        if line.strip():
            cur["free"].append(rename(line.strip(), lang))
    return cards, rows, columns


def bi(zh, en):
    return {"zh": zh, "en": en}


def main() -> int:
    zc, zr, zcol = parse("zh")
    ec, er, ecol = parse("en")
    assert list(zc) == list(ec), "card ids differ between zh and en"
    assert len(zc) == 25, len(zc)
    overlay = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))

    cards = []
    for cid in zc:
        z, e = zc[cid], ec[cid]
        ov = overlay["cards"][cid]
        card = {"id": cid, "column": cid[0], "name": bi(zr[cid]["name"], er[cid]["name"])}
        card.update({k: ov[k] for k in ("kind", "weight", "color", "evidence_level")})
        card["status_line"] = bi(zr[cid]["status_line"], er[cid]["status_line"])
        if "status_line" in ov:  # task-04 rewrite of the one-line status
            card["status_line"] = ov["status_line"]
        for k in ("summary",):
            if k in ov:
                card[k] = ov[k]
        if z["free"]:  # grey card F1 has no numbered items
            card["note"] = bi(" ".join(z["free"]), " ".join(e["free"]))
        for key in ITEM_KEYS:
            if key not in z["items"]:
                continue
            zi, ei = z["items"][key], e["items"][key]
            assert len(zi["bullets"]) == len(ei["bullets"]), (cid, key)
            entry = {"lead": bi(zi["lead"], ei["lead"])}
            if zi["bullets"]:
                entry["bullets"] = [bi(a, b) for a, b in zip(zi["bullets"], ei["bullets"])]
            card[key] = entry
        for k in ("criteria", "needs_b04", "deliverable_dir", "test_report"):
            if k in ov:
                card[k] = ov[k]
        cards.append(card)

    missing = set(overlay["cards"]) ^ set(zc)
    assert not missing, missing
    data = {
        "meta": overlay["meta"],
        "columns": [{"id": c, "name": bi(zcol[c], ecol[c])} for c in zcol],
        "overview_edges": overlay["overview_edges"],
        "cards": cards,
    }

    class Dumper(yaml.SafeDumper):
        pass

    def str_rep(dumper, s):
        style = "|" if "\n" in s else None
        return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=style)

    Dumper.add_representer(str, str_rep)
    body = yaml.dump(data, Dumper=Dumper, allow_unicode=True, sort_keys=False, width=10**6)
    OUT.write_text(HEADER.read_text(encoding="utf-8") + body, encoding="utf-8")
    n_items = sum(1 for c in cards for k in ITEM_KEYS if k in c)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(cards)} cards, {n_items} legacy items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
