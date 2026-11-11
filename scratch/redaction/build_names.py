"""Build the two word lists used by the redaction engines `names_list` and `allowlist`.

Inputs are public files, downloaded by hand into git-ignored folders (see the README of T10 for the URLs):
- 1990 Census first names (dist.female.first, dist.male.first): all distinct names
- 2010 Census surnames (Names_2010Census.csv): the SURNAME_TOP most frequent
- SCOWL 2020.12.07 `final/` (english, american, canadian `-words.` lists up to size SCOWL_MAX; these lists
  hold ordinary words only, proper names are kept by SCOWL in separate files that are not read here)

Outputs (tracked, synthetic/public content only):
- config/person_names.txt   `NAME<TAB>ROLE<TAB>FLAG`; ROLE F = first name, L = surname, FL = both;
                            FLAG N = name only, A = also an ordinary English word (BILL, MARK, PRICE ...),
                            which the redactor masks only in a name context
- config/common_words.txt   one uppercase word per line

Run: uv run python scratch/redaction/build_names.py <dir with dist.*.first> <Names_2010Census.csv> <scowl final dir>
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURNAME_TOP = 30000
SCOWL_MAX = 35

first_dir, surname_csv, scowl = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

words: set[str] = set()
for f in sorted(scowl.iterdir()):
    stem, _, size = f.name.rpartition(".")
    cat, _, kind = stem.partition("-")
    if cat in ("english", "american", "canadian") and kind == "words" and int(size) <= SCOWL_MAX:
        words |= {w.strip() for w in f.read_text(encoding="latin-1").splitlines()}
words = {w.upper() for w in words if w.isascii() and w.isalpha() and w.islower() and len(w) >= 2}

first = {line.split()[0] for f in ("dist.female.first", "dist.male.first") for line in open(first_dir / f) if line.strip()}
first = {n for n in first if n.isalpha() and len(n) >= 2}
last: set[str] = set()
with open(surname_csv, newline="") as fh:
    for row in csv.DictReader(fh):
        if row["name"].isalpha() and len(row["name"]) >= 2:
            last.add(row["name"])
        if len(last) >= SURNAME_TOP:
            break
lines = [f"{n}\t{'F' if n in first else ''}{'L' if n in last else ''}\t{'A' if n in words else 'N'}" for n in sorted(first | last)]

names_out = ROOT / "config" / "person_names.txt"
names_out.write_text(
    "# Person names for the redaction engines names_list / allowlist. Built by scratch/redaction/build_names.py.\n"
    "# Source: US Census Bureau, 1990 Census first names (dist.female.first, dist.male.first) and 2010 Census\n"
    f"# surnames (top {SURNAME_TOP}). US government data, public domain (data.gov lists the surname file as CC0).\n"
    "# NAME<TAB>ROLE (F first, L surname)<TAB>FLAG (N name only, A also an ordinary English word per SCOWL).\n"
    + "\n".join(lines) + "\n")
words_out = ROOT / "config" / "common_words.txt"
words_out.write_text(
    "# Common English words for the redaction engines names_list / allowlist. Built by scratch/redaction/build_names.py.\n"
    f"# Source: SCOWL 2020.12.07 (english/american/canadian word lists up to size {SCOWL_MAX}), uppercased.\n"
    "# Copyright 2000-2018 by Kevin Atkinson. Permission to use, copy, modify, distribute and sell these word lists,\n"
    "# the associated scripts, the output created from the scripts, and its documentation for any purpose is hereby\n"
    "# granted without fee, provided that the above copyright notice appears in all copies and that both that\n"
    "# copyright notice and this permission notice appear in supporting documentation. Kevin Atkinson makes no\n"
    "# representations about the suitability of this array for any purpose. It is provided \"as is\" without express\n"
    "# or implied warranty. (Full notice, including the notices of the source lists: SCOWL `Copyright` file,\n"
    "# http://wordlist.aspell.net/scowl-readme/)\n"
    + "\n".join(sorted(words)) + "\n")
n_a = sum(l.endswith("A") for l in lines)
print(f"first {len(first)}, surnames {len(last)}, names {len(lines)} (ambiguous {n_a}), {names_out.stat().st_size} bytes; "
      f"common words {len(words)}, {words_out.stat().st_size} bytes")
