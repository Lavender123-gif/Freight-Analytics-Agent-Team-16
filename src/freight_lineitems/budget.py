"""Model-call budget ledger (task 09, section 5).

The ledger is an append-only JSONL file tracked in git (`docs/autorun/budget_ledger.jsonl`). It holds usage
counts and dollar figures only, never record text. Every batch run must:
1. call `spent_usd()` and `check_estimate()` before calling the model;
2. call `append_entry()` after the run with the usage it actually measured.

Dollar figures are an API list-price proxy computed from the four token classes, kept separate
(input / output / cache write split by TTL / cache read). They are not an invoice.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "autorun" / "budget_ledger.jsonl"
RESERVATIONS = ROOT / "data" / "interim" / "autorun" / "budget_reservations.json"   # git-ignored; runs in flight
CAP_USD = 110.0   # task 10 section 0: cumulative cap raised from 50 (leg 1 included)

# USD per million tokens. Source: claude-api skill model table (cached 2026-11-03); cache write 5m = 1.25x input,
# 1h = 2x input. Unknown models raise instead of being priced at zero (no silent errors).
PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50, "cache_write_1h": 4.00, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50, "cache_write_1h": 4.00, "cache_read": 0.20},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write_5m": 5.00, "cache_write_1h": 8.00, "cache_read": 0.20},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write_5m": 0.125, "cache_write_1h": 0.20, "cache_read": 0.01},
}
CLASSES = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")


@dataclass
class Usage:
    """Token counts for one model, four classes kept apart (cache write split by TTL)."""
    model: str
    input: int = 0
    output: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    n_calls: int = 0

    def add_response_usage(self, u) -> None:
        """Add the `usage` object of one Messages API response."""
        self.n_calls += 1
        self.input += u.input_tokens or 0
        self.output += u.output_tokens or 0
        self.cache_read += getattr(u, "cache_read_input_tokens", 0) or 0
        cc = getattr(u, "cache_creation", None)
        if cc is not None:
            self.cache_write_5m += getattr(cc, "ephemeral_5m_input_tokens", 0) or 0
            self.cache_write_1h += getattr(cc, "ephemeral_1h_input_tokens", 0) or 0
        else:  # flat field only: assume 5m (the default TTL we use)
            self.cache_write_5m += getattr(u, "cache_creation_input_tokens", 0) or 0

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("model", "n_calls", *CLASSES)}


def cost_usd(usage: dict) -> float:
    p = PRICES.get(usage["model"])
    if p is None:
        raise KeyError(f"no price for model {usage['model']!r}; add it to budget.PRICES before running")
    return sum(usage.get(c, 0) * p[c] for c in CLASSES) / 1_000_000


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def spent_usd() -> float:
    return round(sum(e["cost_usd"] for e in read_ledger()), 6)


def check_estimate(estimate_usd: float, cap: float = CAP_USD) -> tuple[bool, str]:
    """Return (allowed, message). Not allowed when spent + estimate exceeds the cap."""
    spent = spent_usd()
    ok = spent + estimate_usd <= cap
    return ok, f"spent ${spent:.4f} + estimate ${estimate_usd:.4f} = ${spent + estimate_usd:.4f} vs cap ${cap:.2f}"


def append_entry(run_name: str, usages: list[Usage], note: str = "", started_at: str | None = None,
                 n_records: int | None = None, estimate_usd: float | None = None) -> dict:
    parts = [u.as_dict() for u in usages if u.n_calls]
    entry = {
        "run": run_name,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_records": n_records,
        "usage": parts,
        "cost_usd": round(sum(cost_usd(p) for p in parts), 6),
        "estimate_usd": estimate_usd,
        "note": note,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


@dataclass
class UsageBook:
    """Per-model usage for one run (a fallback model, if ever enabled, is booked separately)."""
    by_model: dict[str, Usage] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, model: str, u) -> None:
        with self._lock:
            self.by_model.setdefault(model, Usage(model=model)).add_response_usage(u)

    def usages(self) -> list[Usage]:
        return list(self.by_model.values())

    def cost(self) -> float:
        return sum(cost_usd(u.as_dict()) for u in self.usages())


def _locked(fn):
    """Run fn() under an exclusive file lock shared by all processes of this project."""
    import fcntl
    RESERVATIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(RESERVATIONS.with_suffix(".lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def _read_res() -> dict:
    return json.loads(RESERVATIONS.read_text()) if RESERVATIONS.exists() else {}


def reserve(run_id: str, estimate_usd: float, cap: float = CAP_USD) -> tuple[bool, str]:
    """Check spent + every in-flight reservation + this estimate against the cap, and reserve atomically
    (audit M6: two runs started together each saw the same 'spent' and ignored the other's estimate)."""
    def do():
        res = _read_res()
        held = sum(res.values())
        spent = spent_usd()
        ok = spent + held + estimate_usd <= cap
        if ok:
            res[run_id] = estimate_usd
            RESERVATIONS.write_text(json.dumps(res))
        return ok, (f"spent ${spent:.4f} + in flight ${held:.4f} + estimate ${estimate_usd:.4f} = "
                    f"${spent + held + estimate_usd:.4f} vs cap ${cap:.2f}")
    return _locked(do)


def release(run_id: str) -> None:
    def do():
        res = _read_res()
        res.pop(run_id, None)
        RESERVATIONS.write_text(json.dumps(res))
    _locked(do)
