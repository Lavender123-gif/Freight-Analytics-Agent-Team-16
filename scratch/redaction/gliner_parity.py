"""Parity check: the onnxruntime GLiNER wrapper in redaction_variants.py against the gliner package, on every
fourth generated case (same words masked, protected words aside).
  uv run --with torch --with gliner python scratch/redaction/gliner_parity.py
"""
import json, os, re
os.environ["FL_REDACTION_ENGINE"] = "local_ner"
from freight_lineitems import redaction_variants as RV
from gliner import GLiNER
g = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
cases = [json.loads(l) for l in open("data/interim/redaction/cases.jsonl")][::4]
same = 0
for c in cases:
    t = c["text"]
    ref = [(e["start"], e["end"]) for e in g.predict_entities(t, ["person"], threshold=0.5, flat_ner=False)]
    ref_words = {m.span() for m in re.finditer(r"[A-Za-z]+", t) if any(x < m.end() and m.start() < y for x, y in ref)}
    ours = RV.local_ner_spans(t)
    ours_words = {m.span() for m in re.finditer(r"[A-Za-z]+", t) if any(x < m.end() and m.start() < y for x, y in ours)}
    kinds = {(a, b): k for a, b, _, k in RV._tokens(t)}
    ref_words = {w for w in ref_words if kinds.get(w, "P") not in "PX"}     # our wrapper drops protected words by design
    same += ref_words == ours_words
print("cases", len(cases), "identical word sets", same)
