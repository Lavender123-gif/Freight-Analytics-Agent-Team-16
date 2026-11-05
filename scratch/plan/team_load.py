"""Task 07: per-person load from the WBS hours and the suggested owner/helper split.
Run: uv run --no-project python scratch/plan/team_load.py
Reads hour ranges from docs/plan/2026-11-05_status_and_plan.zh.md section 3.2.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
s = (ROOT / "docs/plan/2026-11-05_status_and_plan.zh.md").read_text()
sec = s.split("### 3.2 工作分解表")[1].split("合计")[0]
H = {}
for r in sec.splitlines():
    if re.match(r"^\| [A-Z]+\d", r):
        c = [x.strip() for x in r.strip("|").split("|")]
        H[c[0]] = tuple(map(int, c[5].split("–")))
Z, R, K, Y, H5 = "Zizhang", "Ron", "Kylie", "Yingxia", "Zhaohan"
ALL = [Z, R, K, Y, H5]
# task: {person: share}
A = {
    "S1": {Z: .7, Y: .3}, "S2": {R: .8, Z: .2}, "S3": {R: .6, Z: .4},
    "P1": {Z: .6, Y: .4}, "P2": {Z: .7, R: .3}, "P3": {R: .8, Z: .2}, "P4": {R: .5, Z: .2, Y: .3},
    "P5": {Z: .6, R: .4},
    "R1": {Y: .6, Z: .4}, "R2": {Z: .6, K: .4}, "R3": {K: .6, Y: .4},
    "M1": {Y: .6, H5: .4}, "M2": {K: .8, Z: .2},
    "L1": {R: .8, Z: .2}, "L2": {Z: .6, R: .4},
    "H1": {Y: .7, K: .3}, "H2": {p: .2 for p in ALL}, "H3": {Y: .7, H5: .3},
    "V1": {Y: .7, R: .3}, "V2": {Y: .6, R: .4}, "V3": {R: .5, Y: .5}, "V4": {Y: .7, R: .3},
    "U1": {K: .5, H5: .5}, "U2": {R: .4, H5: .6}, "U3": {K: .6, H5: .4},
    "G1": {H5: .6, Y: .4}, "K1": {H5: .5, K: .5}, "J01": {K: .8, Z: .2},
    "D1": {K: .6, Z: .1, R: .1, Y: .1, H5: .1}, "D2": {K: .6, Z: .1, R: .1, Y: .1, H5: .1},
    "T1": {Y: 1.0}, "T2": {Z: .6, R: .4}, "T3": {Z: .6, Y: .4},
}
assert set(A) == set(H), set(A) ^ set(H)
for t, sh in A.items():
    assert abs(sum(sh.values()) - 1) < 1e-9, t
tot = {p: [0.0, 0.0] for p in ALL}
for t, sh in A.items():
    for p, f in sh.items():
        tot[p][0] += H[t][0] * f
        tot[p][1] += H[t][1] * f
for p in ALL:
    owner = [t for t, sh in A.items() if max(sh, key=sh.get) == p and sh[p] < 1 and len(sh) < 5 or (sh.get(p) == 1.0)]
    print(f"{p}: {tot[p][0]:.0f}-{tot[p][1]:.0f} h; owns {owner}")
print("sum", sum(v[0] for v in tot.values()), sum(v[1] for v in tot.values()))
crit = ["S1", "S2", "P3", "L1", "V2", "V3", "V4", "D2"]
print("Ron on critical path:", sum(H[t][0] * A[t].get(R, 0) for t in crit), sum(H[t][1] * A[t].get(R, 0) for t in crit))
