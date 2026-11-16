"""Task 19: does the API accept a strict submit_line_items schema variant? One tiny request per variant
(max_tokens 16); the usage is written to the budget ledger. A 400 'grammar too large' costs nothing."""
from __future__ import annotations

import copy
import json
import sys

from freight_lineitems import budget
from freight_lineitems.llm_client import client, request_kwargs
from freight_lineitems.tools import TOOLS

BASE = copy.deepcopy(TOOLS)
NS = {"anyOf": [{"type": "string"}, {"type": "null"}]}


def variant(name: str) -> list[dict]:
    t = copy.deepcopy(BASE)
    s = t[0]["input_schema"]
    for k in ("earlier_claim_mention", "stated_amount_due"):
        s["properties"].pop(k, None)
        s["required"].remove(k)
    if name == "flat3":
        for k in ("earlier_claim_quote", "stated_amount_due_id", "stated_amount_due_evidence"):
            s["properties"][k] = dict(NS, description=k)
            s["required"].append(k)
    if name == "none":
        pass
    return t


def main() -> None:
    names = sys.argv[1:] or ["none", "flat3"]
    cl, kw, book = client(), request_kwargs() | {"max_tokens": 16}, budget.UsageBook()
    for n in names:
        try:
            r = cl.messages.create(tools=variant(n), messages=[{"role": "user", "content": "Reply OK."}], **kw)
            book.add(r.model, r.usage)
            print(n, "accepted", r.stop_reason)
        except Exception as e:  # noqa: BLE001
            print(n, "rejected", str(e)[:160])
    budget.append_entry("t19-schema-probe", book.usages(), note="task 19: strict schema size probe", n_records=0, estimate_usd=0.02)


if __name__ == "__main__":
    main()
