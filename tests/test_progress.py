"""Arithmetic of scratch/plan/progress.py on synthetic input (no project data, no real transcripts)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "progress_script", Path(__file__).resolve().parents[1] / "scratch/plan/progress.py")
progress = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = progress
_spec.loader.exec_module(progress)

CREDIT = {"已验收": 1.0, "已做待验收": 0.7, "未做": 0.0}
PRICES = {"model-a": {"input": 2.0, "output": 10.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "cache_read": 0.1}}


def task(i, lo, hi, owner, status):
    return {"id": i, "hours": [lo, hi], "owner": owner, "status": status, "plan_mode": "cc"}


TASKS = [
    task("T1", 2, 4, "CC", "已验收"),       # median 3
    task("T2", 4, 8, "CC", "已做待验收"),   # median 6
    task("T3", 10, 12, "人工", "未做"),     # median 11
    task("T4", 1, 1, "人工", "已做待验收"),  # median 1
]


def test_median_is_midpoint_of_range():
    assert progress.median_hours(task("X", 3, 5, "CC", "未做")) == 4
    assert progress.median_hours(task("X", 5, 8, "CC", "未做")) == 6.5


def test_workload_and_completion():
    s = progress.summarize(TASKS, CREDIT)
    a = s["all"]
    assert a["hours"] == 21 and a["done_hours"] == 10
    assert a["workload_pct"] == pytest.approx(100 * 10 / 21)
    # accepted counts 100%, done-not-accepted 70%, not done 0
    assert a["earned_hours"] == pytest.approx(3 * 1.0 + 6 * 0.7 + 1 * 0.7)
    assert a["completion_pct"] == pytest.approx(100 * 7.9 / 21)
    assert a["n_by_status"] == {"未做": 1, "已做待验收": 2, "已验收": 1}


def test_split_by_owner_adds_up():
    s = progress.summarize(TASKS, CREDIT)
    assert s["CC"]["hours"] == 9 and s["人工"]["hours"] == 12
    assert s["CC"]["workload_pct"] == pytest.approx(100.0)
    assert s["CC"]["completion_pct"] == pytest.approx(100 * (3 + 4.2) / 9)
    assert s["人工"]["workload_pct"] == pytest.approx(100 * 1 / 12)
    assert s["CC"]["done_hours"] + s["人工"]["done_hours"] == s["all"]["done_hours"]
    assert s["CC"]["earned_hours"] + s["人工"]["earned_hours"] == pytest.approx(s["all"]["earned_hours"])


def test_empty_group_has_no_percentage():
    s = progress.summarize([task("T1", 2, 4, "CC", "未做")], CREDIT)
    assert s["人工"]["workload_pct"] is None and s["人工"]["completion_pct"] is None


def test_assumed_done_only_touches_named_not_done_tasks():
    nxt = progress.with_assumed_done(TASKS, ["T3", "T1"])
    assert [t["status"] for t in nxt] == ["已验收", "已做待验收", "已做待验收", "已做待验收"]
    assert TASKS[2]["status"] == "未做"   # input not mutated
    assert progress.summarize(nxt, CREDIT)["all"]["workload_pct"] == pytest.approx(100.0)
    with pytest.raises(ValueError):
        progress.with_assumed_done(TASKS, ["NOPE"])


def test_validate_rejects_bad_rows():
    progress.validate(TASKS)
    with pytest.raises(ValueError):
        progress.validate([task("T1", 2, 4, "CC", "做了")])
    with pytest.raises(ValueError):
        progress.validate([task("T1", 2, 4, "组员", "未做")])
    with pytest.raises(ValueError):
        progress.validate([task("T1", 5, 4, "CC", "未做")])
    with pytest.raises(ValueError):
        progress.validate([task("T1", 2, 4, "CC", "未做"), task("T1", 2, 4, "CC", "未做")])


def entry(run, n, cost, start, end, **tok):
    u = {"model": "model-a", "n_calls": tok.pop("n_calls", n), "input": 0, "output": 0,
         "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0, **tok}
    return {"run": run, "started_at": start, "finished_at": end, "n_records": n, "usage": [u], "cost_usd": cost}


LEDGER = [
    entry("a-base", 10, 1.0, "2026-01-01T00:00:00+00:00", "2026-01-01T00:10:00+00:00", input=1_000_000),
    entry("a-frep3", 5, 0.5, "2026-01-01T01:00:00+00:00", "2026-01-01T01:10:00+00:00", output=100_000, n_calls=7),
    entry("b-full", 100, 2.0, "2026-01-02T00:00:00+00:00", "2026-01-02T02:00:00+00:00",
          cache_write_5m=400_000, cache_write_1h=250_000, cache_read=1_000_000),
    {"run": "b-empty", "started_at": "2026-01-02T03:00:00+00:00", "finished_at": "2026-01-02T03:01:00+00:00",
     "n_records": 3, "usage": [], "cost_usd": 0},
]


def test_ledger_split_and_totals():
    leg1, leg2 = progress.split_legs(LEDGER, "frep3")
    assert [e["run"] for e in leg1] == ["a-base", "a-frep3"]
    assert [e["run"] for e in leg2] == ["b-full", "b-empty"]
    t1, t2 = progress.ledger_totals(leg1, PRICES), progress.ledger_totals(leg2, PRICES)
    assert (t1["runs"], t1["records"], t1["calls"], t1["cost_usd"]) == (2, 15, 17, 1.5)
    assert t1["tokens"] == {"input": 1_000_000, "output": 100_000, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}
    assert t1["cost_recomputed_usd"] == pytest.approx(2.0 + 1.0)
    assert (t1["first"], t1["last"]) == ("2026-01-01T00:00:00+00:00", "2026-01-01T01:10:00+00:00")
    assert (t2["runs"], t2["records"], t2["calls"]) == (2, 103, 100)
    # classes stay separate; the two cache-write TTLs are priced differently
    assert t2["tokens"]["cache_write_5m"] == 400_000 and t2["tokens"]["cache_write_1h"] == 250_000
    assert t2["cost_recomputed_usd"] == pytest.approx(0.4 * 2.5 + 0.25 * 4.0 + 1.0 * 0.1)
    with pytest.raises(ValueError):
        progress.split_legs(LEDGER, "no-such-run")


def test_ledger_unpriced_model_is_reported_not_priced_at_zero_silently():
    e = entry("x", 1, 0.0, None, None, input=5)
    e["usage"][0]["model"] = "model-unknown"
    t = progress.ledger_totals([e], PRICES)
    assert t["unpriced_models"] == ["model-unknown"] and t["cost_recomputed_usd"] == 0 and t["first"] is None


def test_rate_and_forecast_with_margin():
    rates = {"full": progress.rate_per_record(LEDGER, ["b-full"]), "small": progress.rate_per_record(LEDGER, ["a-"])}
    assert rates["full"]["per_record"] == pytest.approx(0.02)
    assert rates["small"]["per_record"] == pytest.approx(1.5 / 15)
    items = [
        {"when": "next", "name": "n1", "records": 50, "rate": "full"},                    # 1.00
        {"when": "next", "name": "n2", "records": 10, "rate": "small", "optional": True},  # 1.00
        {"when": "later", "name": "l1", "records": 200, "rate": "full"},                  # 4.00
    ]
    fc = progress.forecast(items, rates, 0.4)
    assert fc["next"] == pytest.approx(1.4)
    assert fc["next_optional"] == pytest.approx(1.4)
    assert fc["later"] == pytest.approx(5.6)
    assert fc["later_optional"] == 0
    assert fc["rows"][0]["base_usd"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        progress.rate_per_record(LEDGER, ["nothing"])


def line(mid, model, ts, inp, out, w5=0, w1=0, read=0, flat=None, ttl=True):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": read,
         "cache_creation_input_tokens": w5 + w1 if flat is None else flat}
    if ttl:
        u["cache_creation"] = {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}
    return json.dumps({"type": "assistant", "timestamp": ts, "message": {"id": mid, "model": model, "usage": u}})


def write_session(tmp_path):
    main = tmp_path / "sess-1.jsonl"
    main.write_text("\n".join([
        line("m1", "model-a", "2026-01-01T00:00:01Z", 10, 1, w1=100),          # streaming: first line of m1
        line("m1", "model-a", "2026-01-01T00:00:02Z", 10, 50, w1=100),         # last line of m1 wins
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),
        "not json",
        line("m2", "model-b", "2026-01-01T00:05:00Z", 7, 70, w5=30, read=900),
        line("m3", "<synthetic>", "2026-01-01T00:06:00Z", 999, 999),
    ]) + "\n", encoding="utf-8")
    sub = tmp_path / "sess-1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-x.jsonl").write_text("\n".join([
        line("s1", "model-a", "2026-01-01T00:10:00Z", 1, 2, w5=1000, w1=2000, read=5000),
        line("s1", "model-a", "2026-01-01T00:10:05Z", 1, 20, w5=1000, w1=2000, read=5000),
        line("s2", "model-a", "2026-01-01T00:20:00Z", 3, 4, flat=77, ttl=False),
    ]) + "\n", encoding="utf-8")
    (sub / "agent-x.meta.json").write_text("{}", encoding="utf-8")
    return main


def test_session_dedupes_by_message_id_and_includes_subagents(tmp_path):
    s = progress.cc_session(write_session(tmp_path), PRICES)
    assert s["n_subagent_files"] == 1
    a = s["main"]["by_model"]["model-a"]
    assert (a["messages"], a["input"], a["output"], a["cache_write_1h"], a["cache_write_5m"]) == (1, 10, 50, 100, 0)
    assert "<synthetic>" not in s["main"]["by_model"]
    sa = s["subagents"]["by_model"]["model-a"]
    assert (sa["messages"], sa["input"], sa["output"]) == (2, 4, 24)
    assert (sa["cache_write_5m"], sa["cache_write_1h"], sa["cache_read"]) == (1000, 2000, 5000)
    assert sa["cache_write_ttl_unknown"] == 77      # flat field only: not guessed into a TTL
    al = s["all"]["by_model"]["model-a"]
    assert (al["messages"], al["input"], al["output"]) == (3, 14, 74)
    assert (s["all"]["first"], s["all"]["last"]) == ("2026-01-01T00:00:02Z", "2026-01-01T00:20:00Z")


def test_session_proxy_price_only_for_known_models(tmp_path):
    s = progress.cc_session(write_session(tmp_path), PRICES)
    main_a = s["main"]["by_model"]["model-a"]
    assert main_a["proxy_usd"] == pytest.approx((10 * 2.0 + 50 * 10.0 + 100 * 4.0) / 1e6)
    assert s["main"]["by_model"]["model-b"]["proxy_usd"] is None        # no price: token counts only
    assert s["subagents"]["by_model"]["model-a"]["proxy_usd"] is None   # unknown-TTL cache write: no price


def test_session_flat_field_cross_check(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(line("m1", "model-a", "t", 1, 1, w5=10, w1=20, flat=31) + "\n", encoding="utf-8")
    s = progress.cc_session(p, PRICES)
    assert s["all"]["by_model"]["model-a"]["flat_mismatch"] == 1
    assert s["n_subagent_files"] == 0


def test_unreadable_session_prints_tiny_meter_note(tmp_path):
    assert progress.cc_session(tmp_path / "missing.jsonl", PRICES) is None
    r = {"session": None, "session_asked": True}
    assert progress.NEED_METER in "\n".join(progress.session_section(r))
