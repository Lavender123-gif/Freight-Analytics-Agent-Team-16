"""Screening of local NER candidates before one was wired in as the `local_ner` engine (task 10 section 4).

Raw model output only (no context rules, no clipping), miss rate on the cases written by measure.py.
torch / transformers / gliner are NOT project dependencies; run in a throwaway environment:
  uv run --no-project --python 3.12 --with torch --with transformers --with gliner python scratch/redaction/screen_ner_models.py
Downloads about 3 GB of model weights into the Hugging Face cache. Nothing is sent to an inference API.
"""
import json, sys, time, re
cases = [json.loads(l) for l in open("data/interim/redaction/cases.jsonl")]
def score(name, fn):
    t0=time.time(); miss=0; by={}
    for c in cases:
        a,b = c["span"]; spans = fn(c["text"])
        letters=[i for i in range(a,b) if c["text"][i].isalpha()]
        m = not all(any(x<=i<y for x,y in spans) for i in letters)
        miss+=m; k=c["class"]; by.setdefault(k,[0,0]); by[k][0]+=m; by[k][1]+=1
        g="g:"+c["group"]; by.setdefault(g,[0,0]); by[g][0]+=m; by[g][1]+=1
    print(name, f"miss {miss}/{len(cases)}", {k:f"{v[0]}/{v[1]}" for k,v in sorted(by.items())}, f"{(time.time()-t0)/len(cases)*1000:.1f}s/1000", flush=True)
def widen(text, spans):
    out=[]
    for m in re.finditer(r"[A-Za-z]+", text):
        if any(x<m.end() and m.start()<y for x,y in spans): out.append(m.span())
    return out
from transformers import pipeline
for model in ["dslim/bert-base-NER-uncased", "elastic/distilbert-base-uncased-finetuned-conll03-english"]:
    p = pipeline("token-classification", model=model, aggregation_strategy="simple", device=-1)
    score(model, lambda t: widen(t, [(e["start"], e["end"]) for e in p(t) if e["entity_group"].endswith("PER")]))
for model in ["dslim/bert-base-NER"]:
    p = pipeline("token-classification", model=model, aggregation_strategy="simple", device=-1)
    score(model+" title-cased", lambda t: widen(t, [(e["start"], e["end"]) for e in p(t.title()) if e["entity_group"].endswith("PER")]))
from gliner import GLiNER
for model in ["urchade/gliner_small-v2.1", "urchade/gliner_multi_pii-v1"]:
    g = GLiNER.from_pretrained(model)
    for nm, prep in [("upper", lambda t: t), ("lower", str.lower), ("title", str.title)]:
        score(f"{model} {nm}", lambda t: widen(t, [(e["start"], e["end"]) for e in g.predict_entities(prep(t), ["person"], threshold=0.4)]))
