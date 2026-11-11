"""Aggregate a run (prints aggregates only) and write a row-level detail file to the run's git-ignored folder.

Usage: uv run python scratch/autorun/analyze_run.py <run_id> [--detail]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from statistics import mean

from freight_lineitems.budget import cost_usd
from freight_lineitems.config import RUNS_DIR
from freight_lineitems.sampling import style


def load(run_id: str) -> list[dict]:
    return [json.loads(x) for x in (RUNS_DIR / run_id / "records.jsonl").read_text().splitlines()]


def rec_cost(r: dict) -> float:
    tot = {"model": "claude-sonnet-5-5", "input": 0, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}
    for c in r["process"].get("transcript", {}).get("calls", []):
        u = c["usage"]
        tot["input"] += u.get("input_tokens") or 0
        tot["output"] += u.get("output_tokens") or 0
        tot["cache_read"] += u.get("cache_read_input_tokens") or 0
        cc = u.get("cache_creation") or {}
        tot["cache_write_5m"] += cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens") or 0) or 0
        tot["cache_write_1h"] += cc.get("ephemeral_1h_input_tokens", 0) or 0
    return cost_usd(tot)


def summary(rs: list[dict]) -> dict:
    n = len(rs)
    calls = [r["process"].get("n_model_calls", 0) for r in rs]
    flags = Counter(f["code"] for r in rs for f in r["judgment"]["flags"] if f["severity"] != "info")
    decisive = Counter(c for r in rs for c in r["judgment"]["decisive_flags"])
    tools = Counter(b.get("name") for r in rs for c in r["process"].get("transcript", {}).get("calls", [])
                    for b in c["content"] if b.get("type") == "tool_use")
    return {
        "n": n,
        "recommendation": dict(Counter(r["judgment"]["recommendation"] for r in rs)),
        "parse_status": dict(Counter(r["facts"]["parse_status"] for r in rs)),
        "first_check": dict(Counter(r["facts"]["first_check"] for r in rs)),
        "delta_consistency": dict(Counter(r["facts"]["delta_consistency"] for r in rs)),
        "mean_model_calls": round(mean(calls), 2) if calls else None,
        "mean_attempts": round(mean(len(r["process"].get("attempts", [])) for r in rs), 2),
        "cost_per_record_usd": round(mean(rec_cost(r) for r in rs), 5),
        "decisive_flags": dict(decisive.most_common()),
        "non_info_flags": dict(flags.most_common()),
        "tool_calls": dict(tools),
        "styles": dict(Counter(style(r["facts"]["text_redacted"]) for r in rs)),
    }


def detail(r: dict) -> str:
    f = r["facts"]
    lines = [f"== {r['record_id']}  rec={r['judgment']['recommendation']}  status={f['parse_status']}  "
             f"first={f['first_check']}  final={f['delta_consistency']}  delta={f['source']['delta']}",
             f"   text: {f['text_redacted']}", f"   marked: {f['number_table']['marked_text']}"]
    for a in r["process"].get("attempts", []):
        sub = a["raw_submission"]
        nums = "; ".join(f"{j['id']} {j['kind']}/{j['status']}{'/CR' if j.get('is_credit') else ''} {j['charge_codes']}"
                         for j in sub.get("numbers", []))
        lines.append(f"   attempt {a['attempt_no']} {a['response_type']} check={a['delta_check']} "
                     f"errors={[e['code'] for e in a['repair_errors']]} sum={a['claim'] and a['claim']['signed_sum']}")
        lines.append(f"      numbers: {nums}")
        if sub.get("relations"):
            lines.append(f"      relations: {sub['relations']}")
        if sub.get("reason"):
            lines.append(f"      reason: {sub['reason']}")
    for fl in r["judgment"]["flags"]:
        if fl["severity"] != "info":
            lines.append(f"   flag {fl['severity']}: {fl['code']} {json.dumps(fl['evidence'])[:300]}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    rs = load(a.run_id)
    print(json.dumps(summary(rs), indent=1))
    if a.detail:
        p = RUNS_DIR / a.run_id / "detail.txt"
        p.write_text("\n\n".join(detail(r) for r in rs))
        print("detail ->", p)
