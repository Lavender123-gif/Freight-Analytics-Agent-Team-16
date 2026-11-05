"""A3 deliverable: the design proposal (docs/analysis/02_design_proposal.md) agrees with the prototype's configuration
and with a fresh code-only run on the dev split.

Run from repo root: sh scratch/deliverables/run.sh A3_design_consistency.py
Checks: §4.3 catalog table vs diagnostics_catalog.yaml + rules.yaml (code set, handling, severity/role/points);
§5.3 thresholds vs rules.yaml; §7.2 diagnostic counts and §7.3 dispositions vs a rerun; counts of the D1-D12
decisions, the §10.1 open design choices and the §9.4 experiments. No LLM calls; dev split only.
"""

from __future__ import annotations

import re
from collections import Counter

from _shared import ROOT, md_table, results_dir, run_code_only
from config import CATALOG, RULES

FOLDER = "A3-design-proposal"
doc = (ROOT / "docs" / "analysis" / "02_design_proposal.md").read_text()


def section(start: str, end: str) -> str:
    i = doc.index(start)
    return doc[i:doc.index(end, i + len(start))]


# ---- §4.3 table vs catalog / rules ----
s43 = section("### 4.3 完整清单", "## 5.")
doc_rows = {}
for line in s43.splitlines():
    m = re.match(r"\| `([A-Z]+\.[A-Z]+\.[A-Z0-9_]+)` \|", line)
    if m:
        cells = [c.strip() for c in line.strip("|").split("|")]
        doc_rows[m.group(1)] = (cells[4], cells[5])  # handling, severity/role
codes = [c for c in CATALOG if c != "version"]
drift = []
for c in codes:
    if c not in doc_rows:
        drift.append([c, "missing in 02 §4.3", ""])
        continue
    handling = "退回" if CATALOG[c]["handling"] == "return" else "只记录"
    r = RULES["flags"].get(c)
    sev = f"{r['severity']} / {r['role']}{' +' + str(r['points']) if r.get('points') else ''}" if r else "不生成 flag"
    if doc_rows[c] != (handling, sev):
        drift.append([c, f"doc {doc_rows[c]}", f"config {(handling, sev)}"])
extra_in_doc = sorted(set(doc_rows) - set(codes))

# ---- §5.3 thresholds ----
th = [("escalation.score_threshold", RULES["escalation"]["score_threshold"], 3),
      ("tolerances.amount_abs", RULES["tolerances"]["amount_abs"], 0.005),
      ("tolerances.tax_abs", RULES["tolerances"]["tax_abs"], 0.011),
      ("tolerances.near_105", RULES["tolerances"]["near_105"], [1.03, 1.07]),
      ("tolerances.text_date_after_event_days", RULES["tolerances"]["text_date_after_event_days"], 1),
      ("retry.max_retries", RULES["retry"]["max_retries"], 2),
      ("retry.stop_on_unchanged_resubmission", RULES["retry"]["stop_on_unchanged_resubmission"], True),
      ("agent.max_turns", RULES["agent"]["max_turns"], 12),
      ("agent.reconcile_max_calls", RULES["agent"]["reconcile_max_calls"], 3)]
th_rows = [[f"`{k}`", v, x, "PASS" if v == x else "DIFF"] for k, v, x in th]

# ---- §7.2 / §7.3 vs rerun ----
s72 = section("### 7.2", "### 7.3")
want72 = {m.group(1): (int(m.group(2)), int(m.group(3)), int(m.group(4)))
          for m in re.finditer(r"\| `([A-Z.\d_]+)` \| (\d+) \| (\d+) \| [^|]+ \| (\d+) \|", s72)}
rows, ev, records = run_code_only()
n_rows = {r.source.record_id: len(r.source.source_rows) for r in records}
diag_n, ev_ids = Counter(), {}
for r in records:
    for d in r.diagnostics:
        diag_n[d.code] += 1
        ev_ids.setdefault(d.code, set()).add(r.source.record_id)
r72 = []
for c, (dn, en, rn) in want72.items():
    got = (diag_n[c], len(ev_ids.get(c, ())), sum(n_rows[i] for i in ev_ids.get(c, ())))
    r72.append([f"`{c}`", f"{dn} / {en} / {rn}", f"{got[0]} / {got[1]} / {got[2]}", "PASS" if got == (dn, en, rn) else "DIFF"])
s73 = section("### 7.3", "**LLM 部分")
want73 = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(r"\| `(\w+)`[^|]* \| (\d+) \| [^|]+ \| (\d+) \|", s73)}
disp, disp_rows = Counter(), Counter()
for r in records:
    disp[r.disposition.outcome] += 1
    disp_rows[r.disposition.outcome] += n_rows[r.source.record_id]
r73 = [[k, f"{e} / {rw}", f"{disp[k]} / {disp_rows[k]}", "PASS" if (disp[k], disp_rows[k]) == (e, rw) else "DIFF"]
       for k, (e, rw) in want73.items()]

# ---- structure counts ----
n_d = len(set(re.findall(r"\| \*\*(D\d+'?)\*\*", section("### 1.3", "## 2."))))
n_101 = len(re.findall(r"^\d+\. \*\*", section("### 10.1", "### 10.2"), re.M))
n_102 = len(re.findall(r"^\d+\. \*\*", section("### 10.2", "\n## ") if "\n## " in doc[doc.index("### 10.2"):] else doc[doc.index("### 10.2"):], re.M))
n_e = len(re.findall(r"^\| E\d \|", section("### 9.4", "## 10."), re.M))
struct = [["decisions in §1.3 (D1-D12, incl. D3')", n_d, "13", n_d == 13],
          ["open design choices in §10.1", n_101, "11", n_101 == 11],
          ["questions for the client in §10.2", n_102, "12", n_102 == 12],
          ["experiments in §9.4 (E1-E9)", n_e, "9", n_e == 9],
          ["§4.3 rows found", len(doc_rows), "61", len(doc_rows) == 61],
          ["catalog codes missing from §4.3 or with different handling/role", len(drift), "0", not drift],
          ["§4.3 codes not in the catalog", len(extra_in_doc), "0", not extra_in_doc]]

res = results_dir(FOLDER)
out = ["# A3 design proposal — consistency results\n",
       "Generated by `sh scratch/deliverables/run.sh A3_design_consistency.py`. Rerun on the dev split (908 events, code-only). Not the test set.\n",
       "## Document structure and §4.3 vs configuration\n",
       md_table(["check", "value", "expected", "pass"], [[a, b, c, "PASS" if d else "FAIL"] for a, b, c, d in struct]),
       ("\n" + md_table(["code", "02 §4.3", "configuration"], drift) if drift else ""),
       "\n## §5.3 thresholds vs rules.yaml\n", md_table(["key", "rules.yaml", "02 §5.3", "check"], th_rows),
       "\n## §7.2 diagnostic counts vs rerun (diagnostics / events / rows)\n", md_table(["code", "02 §7.2", "rerun", "check"], r72),
       "\n## §7.3 dispositions vs rerun (events / rows)\n", md_table(["outcome", "02 §7.3", "rerun", "check"], r73)]
(res / "summary.md").write_text("\n".join(out))
print("\n".join(out))
