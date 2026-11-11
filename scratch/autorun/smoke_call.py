"""Stage 0 step 5: one minimal real call to confirm the key, model id and settings work. No record data is sent.

Run: uv run python scratch/autorun/smoke_call.py
"""

from datetime import datetime, timezone

from freight_lineitems import budget
from freight_lineitems.llm_client import client, request_kwargs

started = datetime.now(timezone.utc).isoformat(timespec="seconds")
ok, msg = budget.check_estimate(0.01)
print("budget:", msg)
assert ok
kw = request_kwargs() | {"max_tokens": 50}
r = client().messages.create(messages=[{"role": "user", "content": "Reply with the single word: ready"}], **kw)
book = budget.UsageBook()
book.add(r.model, r.usage)
print("model:", r.model, "| stop_reason:", r.stop_reason)
print("text:", " ".join(b.text for b in r.content if b.type == "text"))
e = budget.append_entry("stage0-smoke", book.usages(), note="minimal connectivity check, no record data", started_at=started,
                        n_records=0, estimate_usd=0.01)
print("usage:", e["usage"], "cost_usd:", e["cost_usd"])
