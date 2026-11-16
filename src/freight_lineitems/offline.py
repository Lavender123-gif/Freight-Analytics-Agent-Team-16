"""Run a batch through the whole pipeline with stored readings in place of the model (task 20 section 2.8).

Every step except the model call is the production code: reading the input file, merging order copies, preparation
(normalising, redaction, number table), the reading checks (each stored reading is submitted through the same
`submit_line_items` check the model's submission goes through), flags and recommendation, then
`pipeline.finish_batch` (copies, shipment roll-up, client names) and `pipeline.write_outputs` (records, shipments,
shipment table, SQLite, exports). Nothing is sent anywhere and no key is needed. The screening call is a model call
and is skipped; the run record says so.

Use it for the smoke test of a clean checkout, or to replay readings stored from an earlier run.

    uv run python -m freight_lineitems.offline --input tests/fixtures/smoke/batch.csv \
        --readings tests/fixtures/smoke/readings.json --name smoke

`--readings`: a JSON object mapping a row number of the input file (0-based, as a string) to a reading in the
`submit_line_items` format. Only the first row of an explanation is read (order copies share its reading). An
explanation with no stored reading gets the flags a missing model answer gets.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path

from freight_lineitems.agent import Session
from freight_lineitems.config import RUNS_DIR
from freight_lineitems.pipeline import assemble, finish_batch, prepare, run_record, write_outputs
from freight_lineitems.records import InputRecord, group_explanations, load_csv

OFFLINE_MODEL = "offline-stored-readings"


def read_one(prep: dict, reading: dict | None) -> dict:
    """One explanation with a stored reading: the reading goes through Session.submit (the real checks)."""
    sess = Session(ctx=prep["ctx"], llm_input=prep["llm_input"])
    if reading is not None:
        sess.submit(json.loads(json.dumps(reading)))
    tr = {"calls": [], "events": [], "first_user_message": None}
    return assemble(prep, {"session": sess, "transcript": tr, "routing": {"layout": "offline"}})


def run_offline(records: list[InputRecord], readings: dict[str, dict], run_name: str,
                runs_dir: Path = RUNS_DIR) -> tuple[str, list[dict], list[dict], Path]:
    """Run the batch with stored readings. Returns (run_id, results, shipments, output folder)."""
    reps = [g[0] for g in group_explanations(records)]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + run_name + "-" + uuid.uuid4().hex[:4]
    out_dir = runs_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [read_one(prepare(r), readings.get(r.record_id)) for r in reps]
    results, ships = finish_batch(records, results)
    settings = {"model": OFFLINE_MODEL}
    write_outputs(out_dir, run_id, run_name, records, results, ships, settings)
    (out_dir / "run_info.json").write_text(json.dumps({
        "run_id": run_id, "n_records": len(records), "n_explanations": len(reps), "n_shipments": len(ships),
        "mode": "offline: stored readings, no model call, screening skipped",
        "run_record": run_record(settings) | {"screening_enabled": False}}, indent=1, default=str))
    return run_id, results, ships, out_dir


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", required=True, help="CSV in the AutoPay column layout (see records.EXPECTED_COLUMNS)")
    ap.add_argument("--readings", required=True, help="JSON: record id -> stored reading")
    ap.add_argument("--name", default="offline")
    ap.add_argument("--out", default=None, help=f"folder for the run (default {RUNS_DIR})")
    a = ap.parse_args(argv)
    records = load_csv(Path(a.input), prefix=a.name)
    readings = {f"{a.name}#r{k}": v for k, v in json.loads(Path(a.readings).read_text()).items()}
    run_id, results, ships, out = run_offline(records, readings, a.name, Path(a.out) if a.out else RUNS_DIR)
    recs = {}
    for r in results:
        recs[r["judgment"]["recommendation"]] = recs.get(r["judgment"]["recommendation"], 0) + 1
    print(json.dumps({"run_id": run_id, "rows": len(records), "explanations": len(results), "shipments": len(ships),
                      "explanation_recommendations": recs,
                      "files": sorted(p.name for p in out.iterdir())}, indent=1))


if __name__ == "__main__":
    main()
