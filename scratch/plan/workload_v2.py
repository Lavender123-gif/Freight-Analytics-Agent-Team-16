"""Task 08: workload v2 — tiers, budget scenarios, critical path, comparison with task 07.
Run: uv run --no-project python scratch/plan/workload_v2.py
Single source for the numbers in docs/plan/2026-11-05_workload_v2.zh.md and 2026-11-05_debrief.zh.md.
With --check, also verifies that the task table in the workload file matches T below.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGET = 80  # four members x ~20 h
WEEKS = 4    # 2026-11-05 .. 2026-12-03

# id: (line, tier, lo, hi, difficulty, mode, deps, old_ids)
# tier: must | should | skip ; mode: cc = code written with Claude Code, human = manual work
T = {
    "S1":  ("schema", "must", 3, 5, "高", "human", [], ["S1"]),
    "S2":  ("schema", "must", 6, 10, "高", "cc", ["S1"], ["S2", "S3"]),
    "P1":  ("proto", "should", 4, 6, "低", "human", [], ["P1"]),
    "P2":  ("proto", "must", 2, 4, "中", "cc", [], ["P2"]),
    "P3":  ("proto", "must", 4, 8, "高", "cc", ["S1", "P2"], ["P3"]),
    "P4a": ("proto", "must", 5, 8, "中", "cc", [], ["P4"]),
    "P4b": ("proto", "should", 4, 6, "中", "cc", ["P3"], ["P4"]),
    "P5":  ("proto", "must", 3, 5, "中", "cc", ["S2", "P2"], ["P5"]),
    "R1a": ("rules", "must", 4, 6, "中", "cc", ["S2", "P2"], ["R1"]),
    "R1b": ("rules", "must", 4, 7, "中", "cc", ["R1a", "M1"], ["R1"]),
    "R1c": ("rules", "should", 3, 5, "中", "cc", ["R1b"], ["R1"]),
    "R2":  ("rules", "should", 2, 3, "中", "cc", ["R1a"], ["R2"]),
    "R3":  ("rules", "skip", 1, 2, "低", "human", ["R1a"], ["R3"]),
    "M1":  ("mock", "must", 5, 8, "中", "cc", [], ["M1"]),
    "L1":  ("model", "must", 8, 12, "高", "cc", ["S2", "P3", "P4a"], ["L1", "S3"]),
    "L2":  ("model", "must", 4, 6, "中", "cc", ["P3"], ["L2"]),
    "H1":  ("human", "must", 3, 5, "低", "human", ["S1"], ["H1"]),
    "H2a": ("human", "must", 10, 14, "低", "human", ["H1"], ["H2"]),
    "H2b": ("human", "should", 10, 14, "低", "human", ["H2a"], ["H2"]),
    "H3":  ("human", "must", 3, 5, "中", "cc", ["H2a", "L1"], ["H3"]),
    "V1":  ("eval", "must", 4, 6, "中", "cc", ["M1"], ["V1", "M2"]),
    "V3a": ("eval", "must", 4, 6, "高", "cc", ["L1", "V1"], ["V3", "V2"]),
    "V3b": ("eval", "should", 2, 4, "中", "cc", ["V3a"], ["V3"]),
    "V3c": ("eval", "skip", 3, 5, "中", "cc", ["V3a", "R1c"], ["V3"]),
    "V4":  ("eval", "must", 2, 3, "高", "human", ["V3a", "H3"], ["V4"]),
    "U1":  ("ui", "must", 3, 5, "低", "human", [], ["U1"]),
    "U2":  ("ui", "must", 10, 16, "高", "cc", ["U1", "P5", "R1a"], ["U2"]),
    "U3":  ("ui", "should", 2, 3, "低", "human", ["U2"], ["U3"]),
    "U4":  ("ui", "skip", 8, 12, "中", "cc", ["U2", "R1c"], []),
    "G1":  ("other", "skip", 4, 6, "中", "cc", ["S2"], ["G1"]),
    "K1":  ("docs", "must", 3, 5, "低", "human", ["L2"], ["K1"]),
    "J01": ("client", "must", 4, 6, "低", "human", [], ["J01"]),
    "D1":  ("present", "must", 5, 8, "低", "human", [], ["D1"]),
    "D2":  ("present", "must", 14, 22, "高", "human", ["V4", "U2"], ["D2"]),
    "T1":  ("other", "should", 1, 2, "低", "human", [], ["T1"]),
    "T2":  ("other", "skip", 2, 4, "中", "cc", [], ["T2"]),
    "T3":  ("other", "skip", 2, 3, "低", "human", [], ["T3"]),
}
OVERHEAD = (10, 20)  # X1: weekly meetings, board upkeep; 5 people x 4 weeks x 30-60 min
U2_ALT = {"A": (5, 8), "B": (3, 5)}  # A: open-source tool config; B: static HTML + Excel decisions

OLD = {  # task 07 section 3.2
    "S1": (4, 6), "S2": (16, 24), "S3": (10, 16), "P1": (6, 10), "P2": (6, 10), "P3": (10, 16),
    "P4": (14, 20), "P5": (6, 10), "R1": (12, 18), "R2": (4, 8), "R3": (2, 4), "M1": (10, 16),
    "M2": (2, 4), "L1": (16, 24), "L2": (8, 12), "H1": (6, 10), "H2": (30, 40), "H3": (6, 10),
    "V1": (10, 14), "V2": (6, 10), "V3": (16, 24), "V4": (4, 6), "U1": (6, 10), "U2": (24, 40),
    "U3": (4, 6), "G1": (8, 12), "K1": (6, 10), "J01": (6, 10), "D1": (8, 12), "D2": (24, 36),
    "T1": (2, 4), "T2": (4, 8), "T3": (4, 6),
}
OLD_CODE = {"S2", "S3", "P2", "P3", "P4", "P5", "R1", "R2", "L1", "L2", "V1", "V2", "V3", "U2", "G1", "T2", "M1", "H3"}


def s(ids, k=None):
    lo = sum(T[i][2] for i in ids)
    hi = sum(T[i][3] for i in ids)
    return lo, hi


def fmt(p):
    return f"{p[0]}–{p[1]}"


def main():
    assert len(OLD) == 33
    covered = {o for v in T.values() for o in v[7]}
    assert covered == set(OLD), set(OLD) ^ covered
    for i, v in T.items():
        for d in v[6]:
            assert d in T, (i, d)
    tiers = {t: [i for i in T if T[i][1] == t] for t in ("must", "should", "skip")}
    print("== tiers")
    for t, ids in tiers.items():
        print(t, len(ids), fmt(s(ids)))
    allp = s(T)
    print("all", len(T), fmt(allp), "+ overhead", fmt(OVERHEAD), "=", fmt((allp[0] + OVERHEAD[0], allp[1] + OVERHEAD[1])))

    print("== must by difficulty / mode")
    for d in ("低", "中", "高"):
        ids = [i for i in tiers["must"] if T[i][4] == d]
        print(d, len(ids), fmt(s(ids)), ids)
    for m in ("cc", "human"):
        ids = [i for i in tiers["must"] if T[i][5] == m]
        print(m, len(ids), fmt(s(ids)))

    print("== by line x tier")
    lines = []
    for v in T.values():
        if v[0] not in lines:
            lines.append(v[0])
    for ln in lines:
        row = []
        for t in ("must", "should", "skip"):
            ids = [i for i in tiers[t] if T[i][0] == ln]
            row.append(f"{len(ids)}:{fmt(s(ids))}" if ids else "-")
        print(ln, row)

    print("== scenarios (total incl. overhead; user = total - 80)")
    must = s(tiers["must"])
    four = ["P1", "V3b", "U3", "R2"]
    sc = {
        "1 must": must,
        "2 must + P1 V3b U3 R2": tuple(a + b for a, b in zip(must, s(four))),
        "3 must + all should": tuple(a + b for a, b in zip(must, s(tiers["should"]))),
    }
    for name, p in sc.items():
        tot = (p[0] + OVERHEAD[0], p[1] + OVERHEAD[1])
        user = (tot[0] - BUDGET, tot[1] - BUDGET)
        mid = (user[0] + user[1]) / 2
        print(name, "tasks", fmt(p), "total", fmt(tot), "user", fmt(user), f"mid {mid:.0f}",
              f"per week {user[0] / WEEKS:.0f}–{user[1] / WEEKS:.0f}")
    u2 = (T["U2"][2], T["U2"][3])
    for k, a in U2_ALT.items():
        print(f"U2 alt {k} saves {u2[0] - a[0]}–{u2[1] - a[1]}")
    # members can absorb without coding: human-mode must tasks + overhead
    hm = s([i for i in tiers["must"] if T[i][5] == "human"])
    print("must human-mode", fmt(hm))

    print("== critical path (longest chain, lo and hi)")
    for k in (2, 3):
        memo = {}

        def ef(i):
            if i not in memo:
                memo[i] = max((ef(d)[0] for d in T[i][6]), default=0) + T[i][k], i
            return memo[i]
        best = {}

        def chain(i):
            deps = T[i][6]
            if not deps:
                return [i]
            d = max(deps, key=lambda x: ef(x)[0])
            return chain(d) + [i]
        must_ids = tiers["must"]
        end = max(must_ids, key=lambda i: ef(i)[0])
        print("lo" if k == 2 else "hi", ef(end)[0], chain(end))
        for e in ("U2", "L1", "V4", "H3"):
            print("   EF", e, ef(e)[0], chain(e))

    print("== vs task 07")
    old_all = (sum(v[0] for v in OLD.values()), sum(v[1] for v in OLD.values()))
    print("old", fmt(old_all), "new (no overhead)", fmt(allp),
          f"change {100 * (allp[0] / old_all[0] - 1):.0f}% / {100 * (allp[1] / old_all[1] - 1):.0f}%")
    oc = (sum(OLD[o][0] for o in OLD_CODE), sum(OLD[o][1] for o in OLD_CODE))
    oh = (old_all[0] - oc[0], old_all[1] - oc[1])
    new_code = [i for i in T if any(o in OLD_CODE for o in T[i][7])]
    new_hum = [i for i in T if T[i][7] and not any(o in OLD_CODE for o in T[i][7])]
    nc, nh = s(new_code), s(new_hum)
    print("code-heavy old", fmt(oc), "-> new", fmt(nc), new_code)
    print("manual old", fmt(oh), "-> new", fmt(nh), new_hum)
    print("added (U4)", fmt(s([i for i in T if not T[i][7]])))

    if "--check" in sys.argv:
        doc = (ROOT / "docs/plan/2026-11-05_workload_v2.zh.md").read_text()
        seen = {}
        tiername = {"必须做": "must", "应该做": "should", "可以不做": "skip"}
        for r in doc.splitlines():
            m = re.match(r"^\| \*\*([A-Z]+\d*[a-c]?|J01)\*\* \|", r)
            if m:
                c = [x.strip() for x in r.strip("|").split("|")]
                lo, hi = map(int, re.match(r"(\d+)–(\d+)", c[3]).groups())
                seen[m.group(1)] = (tiername[c[2]], lo, hi, c[4])
        bad = 0
        for i, v in T.items():
            got = seen.get(i)
            want = (v[1], v[2], v[3], v[4])
            if got != want:
                print("MISMATCH", i, "doc", got, "data", want)
                bad += 1
        extra = set(seen) - set(T)
        if extra:
            print("EXTRA in doc", extra)
            bad += 1
        print(f"check: {len(seen)} rows in doc, {bad} problems")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
