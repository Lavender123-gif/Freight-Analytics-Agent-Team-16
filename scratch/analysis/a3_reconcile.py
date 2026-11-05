"""How does Delta relate to the numbers in the text? (aggregates only)

Each row gets the FIRST matching relation in the order below.
Relations are computed over number tokens after removing dates and times
(see common.number_tokens). Weights, ZIP codes, etc. remain as tokens, so a
coincidental match is possible; that is acknowledged in the report.
"""

from itertools import combinations

from common import EPS, load_dev, number_tokens

df = load_dev()


def close(a: float, b: float) -> bool:
    return abs(a - b) <= EPS


def relation(text: str, delta: float) -> str:
    if text == "":
        return "R0 empty text"
    toks = number_tokens(text)
    vals = [t["value"] for t in toks]
    dollars = [t["value"] for t in toks if t["has_dollar"]]
    if not vals:
        return "R1 no number in text"
    if close(delta, 0):
        return "R2 Delta = 0 (text has numbers)"
    if len(vals) == 1 and close(vals[0], abs(delta)):
        return "R3 single number = |Delta|"
    if close(vals[-1], abs(delta)):
        return "R4 last number = |Delta| (multi-number text)"
    if any(close(v, abs(delta)) for v in vals):
        return "R5 some non-last number = |Delta|"
    if dollars and close(sum(dollars), delta):
        return "R6 sum of $ amounts = Delta"
    if close(sum(vals), delta):
        return "R7 sum of all numbers = Delta"
    if any(close(2 * v, delta) for v in vals):
        return "R8 Delta = 2 x a stated number"
    for k in range(2, min(len(vals), 5) + 1):
        for combo in combinations(vals, k):
            if close(sum(combo), delta):
                return "R9 Delta = sum of a subset of numbers"
    return "R10 no relation found"


df["rel"] = [relation(t, d) for t, d in zip(df.text_norm, df.Delta)]
n = len(df)
print(f"rows {n}")
for k, v in df.rel.value_counts().sort_index().items():
    print(f"{k:50s} {v:4d} ({v / n:.1%})")

# Rows where Delta is NOT equal to a single stated amount and not obviously the total.
hard = df.rel.str[:3].isin(["R5 ", "R6 ", "R7 ", "R8 ", "R9 ", "R10"]) | (df.rel.str[:3] == "R10")
print(f"\nrows where Delta != single or last stated number (R5-R10): {hard.sum()} ({hard.mean():.1%})")
print("by carrier:", df[hard].carrier.value_counts().to_dict())

# Texts with more than one number: how often is Delta the last one?
multi = df.text_norm.map(lambda t: len(number_tokens(t)) > 1)
print(f"\ntexts with >1 number token: {multi.sum()}")
print(df[multi].rel.value_counts().sort_index().to_string())

# Doubling: Delta = 2 x the text's final stated total, among all rows
dbl = [
    any(close(2 * t["value"], d) for t in number_tokens(x)) and not close(d, 0)
    for x, d in zip(df.text_norm, df.Delta)
]
print(f"\nrows where Delta = 2 x some stated number (any order): {sum(dbl)}")
