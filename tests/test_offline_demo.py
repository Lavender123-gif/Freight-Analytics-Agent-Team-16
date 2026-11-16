"""The offline demo (scratch/demo/build_offline_demo.py) keeps showing what its comments say it shows.

No model call and no data files: hand-written readings run through the real pipeline (via freight_lineitems.offline
pieces) into a temporary folder. If a rule change moves a demo record to another colour, this test fails and the
demo's description must be revisited."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scratch" / "demo" / "build_offline_demo.py"


def _run(tmp_path) -> dict[str, dict]:
    spec = importlib.util.spec_from_file_location("build_offline_demo", SCRIPT)
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    demo.main(["--runs-dir", str(tmp_path)])
    lines = (tmp_path / demo.RUN_ID / "records.jsonl").read_text().splitlines()
    return {json.loads(x)["record_id"].rsplit("#r", 1)[1]: json.loads(x) for x in lines}


def _flags(rec) -> dict[str, str]:
    return {f["code"]: f["severity"] for f in rec["judgment"]["flags"]}


def test_demo_records_land_on_the_colours_they_are_written_for(tmp_path):
    got = _run(tmp_path)
    rec = {k: v["judgment"]["recommendation"] for k, v in got.items()}
    assert [rec[k] for k in ("0", "1", "2", "4", "6")] == ["PASSED_CHECKS"] * 5   # plain claims, a sum, detention with distractors
    assert rec["5"] == "HUMAN_REVIEW"                                              # credit and tax in one text
    assert rec["7"] == rec["8"] == "RETURN_SUGGESTED"                              # empty text, digits only
    assert rec["9"] == rec["10"] == rec["12"] == "HUMAN_REVIEW"                    # no number, instruction-like, evidence not in text
    assert rec["11"] == "PASSED_CHECKS"                                            # a name was replaced before reading
    assert set(rec.values()) == {"PASSED_CHECKS", "HUMAN_REVIEW", "RETURN_SUGGESTED"}


def test_demo_flags_are_the_ones_the_demo_describes(tmp_path):
    got = _run(tmp_path)
    assert _flags(got["7"]) == {"REC.TEXT.EMPTY": "return"}
    assert _flags(got["8"])["REC.TEXT.NUMBERS_ONLY"] == "return"
    assert _flags(got["9"])["REC.TEXT.NO_NUMBER"] == "attention"
    assert _flags(got["10"])["REC.TEXT.INJECTION_SUSPECT"] == "attention"
    assert _flags(got["11"]) == {"REC.TEXT.PII_REDACTED": "info"}
    assert "RUN.SUBMIT.NONE" in _flags(got["12"])                                  # the reading never passed the checks
