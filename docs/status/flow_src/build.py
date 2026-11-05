"""Build the pipeline flow diagram from flow.yaml into two self-contained HTML files (zh, en).

Run from repo root:  uv run --with pyyaml python docs/status/flow_src/build.py
Writes docs/status/pipeline_flow.zh.html and docs/status/pipeline_flow.en.html.
No network, no external fonts or scripts: inline SVG + CSS only.
"""

from __future__ import annotations

import html
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
SRC = yaml.safe_load((HERE / "flow.yaml").read_text(encoding="utf-8"))

LANE_HEAD = 132   # width of the lane-name column
LANE_H = 128
COL_W = 190
NODE_W, NODE_H = 150, 66
TOP = 46          # room for stage bands
RIGHT_PAD = 96

COLOURS = {  # fill, stroke, text
    "green": ("#e3f4e6", "#2e7d32", "#1b3d1f"),
    "yellow": ("#fff6d1", "#b8860b", "#4d3800"),
    "red": ("#fbe1e0", "#c62828", "#4a1010"),
    "grey": ("#ececec", "#777777", "#333333"),
    None: ("#ffffff", "#8a94a6", "#1f2937"),
}
LEGEND = {
    "zh": {"green": "完成，有交付物", "yellow": "部分完成", "red": "未开始", None: "不对应卡片",
           "normal": "主流程", "branch": "分支", "return": "回到前面"},
    "en": {"green": "done, deliverable", "yellow": "partial", "red": "not started", None: "no card",
           "normal": "main flow", "branch": "branch", "return": "goes back"},
}

lane_idx = {ln["id"]: i for i, ln in enumerate(SRC["lanes"])}
n_cols = max(n["col"] for n in SRC["nodes"]) + 1
W = LANE_HEAD + n_cols * COL_W + RIGHT_PAD
H = TOP + len(SRC["lanes"]) * LANE_H + 8


def col_x(c: float) -> float:
    """x of the centre of column c (fractional columns allowed)."""
    return LANE_HEAD + c * COL_W + COL_W / 2


def lane_y(lane: str, frac: float = 0.5) -> float:
    return TOP + lane_idx[lane] * LANE_H + frac * LANE_H


nodes = {n["id"]: n for n in SRC["nodes"]}
for n in nodes.values():
    n["cx"], n["cy"] = col_x(n["col"]), lane_y(n["lane"])


def anchor(n: dict, toward: tuple[float, float]) -> tuple[float, float, tuple[int, int]]:
    """Point on the node border facing `toward`, and the outward normal."""
    dx, dy = toward[0] - n["cx"], toward[1] - n["cy"]
    if abs(dx) * NODE_H > abs(dy) * NODE_W:
        s = 1 if dx > 0 else -1
        return n["cx"] + s * NODE_W / 2, n["cy"], (s, 0)
    s = 1 if dy > 0 else -1
    return n["cx"], n["cy"] + s * NODE_H / 2, (0, s)


def edge_path(e: dict) -> tuple[str, tuple[float, float]]:
    a, b = nodes[e["from"]], nodes[e["to"]]
    via = [(col_x(c), lane_y(ln, f)) for c, ln, f in e.get("via", [])]
    if via:
        x1, y1, _ = anchor(a, via[0])
        x2, y2, _ = anchor(b, via[-1])
        pts = [(x1, y1)] + via + [(x2, y2)]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        mid_seg = len(pts) // 2
        (mx1, my1), (mx2, my2) = pts[mid_seg - 1], pts[mid_seg]
        return d, ((mx1 + mx2) / 2, (my1 + my2) / 2)
    x1, y1, n1 = anchor(a, (b["cx"], b["cy"]))
    x2, y2, n2 = anchor(b, (a["cx"], a["cy"]))
    k = max(36.0, (abs(x2 - x1) + abs(y2 - y1)) / 3)
    c1 = (x1 + n1[0] * k, y1 + n1[1] * k)
    c2 = (x2 + n2[0] * k, y2 + n2[1] * k)
    d = f"M {x1:.1f} {y1:.1f} C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {x2:.1f} {y2:.1f}"
    if abs(y2 - y1) < 1:  # straight edge between neighbours in one lane: label below the nodes, not on them
        return d, ((x1 + x2) / 2, y1 + NODE_H / 2 + 14)
    mx = 0.125 * x1 + 0.375 * c1[0] + 0.375 * c2[0] + 0.125 * x2
    my = 0.125 * y1 + 0.375 * c1[1] + 0.375 * c2[1] + 0.125 * y2
    return d, (mx, my)


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def text_w(s: str, size: float) -> float:
    """Rough rendered width: CJK ~1 em, other characters ~0.56 em."""
    return sum(size if ord(ch) > 0x2E80 else size * 0.56 for ch in s)


def render(lang: str) -> str:
    L = LEGEND[lang]
    svg: list[str] = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
               f'aria-label="{esc(SRC["title"][lang])}">')
    svg.append('<defs>'
               '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               '<path d="M0 0 L10 5 L0 10 z" fill="#4b5563"/></marker>'
               '<marker id="arrow-b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               '<path d="M0 0 L10 5 L0 10 z" fill="#b45309"/></marker>'
               '<marker id="arrow-r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               '<path d="M0 0 L10 5 L0 10 z" fill="#2563eb"/></marker></defs>')
    # stage bands
    for i, st in enumerate(SRC["stages"]):
        x0 = LANE_HEAD + st["from"] * COL_W + 3
        x1 = LANE_HEAD + (st["to"] + 1) * COL_W - 3
        svg.append(f'<rect class="stage s{i % 2}" x="{x0}" y="6" width="{x1 - x0}" height="{H - 12}" rx="10"/>')
        svg.append(f'<text class="stage-label" x="{(x0 + x1) / 2}" y="28">{esc(st[lang])}</text>')
    # lanes
    for i, ln in enumerate(SRC["lanes"]):
        y = TOP + i * LANE_H
        svg.append(f'<rect class="lane l{i % 2}" x="4" y="{y}" width="{W - 8}" height="{LANE_H}"/>')
        fs = min(13.0, 13.0 * (LANE_HEAD - 16) / (text_w(ln[lang], 13) * 1.08))
        svg.append(f'<text class="lane-label" x="{LANE_HEAD / 2}" y="{y + LANE_H / 2 + 5}" font-size="{fs:.1f}">{esc(ln[lang])}</text>')
    svg.append(f'<line class="lane-sep" x1="{LANE_HEAD}" y1="{TOP}" x2="{LANE_HEAD}" y2="{TOP + len(SRC["lanes"]) * LANE_H}"/>')
    # edges (under nodes), labels collected for a top layer
    labels = []
    for e in SRC["edges"]:
        kind = e.get("kind", "normal")
        d, (mx, my) = edge_path(e)
        ox, oy = e.get("label_offset", (0, 0))
        mx, my = mx + ox, my + oy
        marker = {"normal": "arrow", "branch": "arrow-b", "return": "arrow-r"}[kind]
        svg.append(f'<path class="edge {kind}" d="{d}" marker-end="url(#{marker})">'
                   f'<title>{esc(nodes[e["from"]][lang])} → {esc(nodes[e["to"]][lang])}: {esc(e[lang])}</title></path>')
        lab = e[lang]
        w = text_w(lab, 11) + 10
        labels.append(f'<g class="elabel {kind}"><rect x="{mx - w / 2:.1f}" y="{my - 9:.1f}" width="{w:.1f}" height="17" rx="4"/>'
                      f'<text x="{mx:.1f}" y="{my + 4:.1f}">{esc(lab)}</text></g>')
    # nodes
    for n in nodes.values():
        st = SRC["status"].get(n.get("card"))
        fill, stroke, ink = COLOURS[st]
        x, y = n["cx"] - NODE_W / 2, n["cy"] - NODE_H / 2
        title = f'{n[lang]} — {n["sub"][lang]}' + (f' [{n["card"]}]' if n.get("card") else "")
        svg.append(f'<g class="node"><title>{esc(title)}</title>'
                   f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="9" fill="{fill}" stroke="{stroke}"/>')
        if n.get("card"):
            svg.append(f'<text class="card" x="{x + NODE_W - 7}" y="{y + 13}" fill="{stroke}">{esc(n["card"])}</text>')
        if n.get("tag"):
            tw = text_w(n["tag"][lang], 10) + 10
            svg.append(f'<rect class="tag" x="{x + 6}" y="{y - 8}" width="{tw:.1f}" height="15" rx="7"/>'
                       f'<text class="tagt" x="{x + 6 + tw / 2:.1f}" y="{y + 3}">{esc(n["tag"][lang])}</text>')
        fs = min(10.5, 10.5 * (NODE_W - 12) / text_w(n["sub"][lang], 10.5))  # shrink long subtitles to fit
        fl = min(13.0, 13.0 * (NODE_W - 12) / (text_w(n[lang], 13) * 1.08))
        svg.append(f'<text class="nlabel" x="{n["cx"]}" y="{n["cy"] - 3}" fill="{ink}" font-size="{fl:.1f}">{esc(n[lang])}</text>'
                   f'<text class="nsub" x="{n["cx"]}" y="{n["cy"] + 15}" fill="{ink}" font-size="{fs:.1f}">{esc(n["sub"][lang])}</text></g>')
    svg += labels
    svg.append("</svg>")

    legend = "".join(
        f'<span class="lg"><i style="background:{COLOURS[k][0]};border-color:{COLOURS[k][1]}"></i>{esc(L[k])}</span>'
        for k in ["green", "yellow", "red", None])
    legend += "".join(f'<span class="lg"><b class="ln {k}"></b>{esc(L[k])}</span>' for k in ["normal", "branch", "return"])
    notes = "".join(f"<li>{esc(t)}</li>" for t in SRC["notes"][lang])
    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="docs/status/flow_src/build.py ({esc(SRC['version'])})">
<title>{esc(SRC['title'][lang])}</title>
<style>
  body {{ margin: 0; padding: 20px 24px 32px; background: #f8fafc; color: #1f2937;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ font-size: 13px; color: #6b7280; margin-bottom: 10px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; margin: 6px 0 12px; }}
  .lg {{ display: inline-flex; align-items: center; gap: 6px; }}
  .lg i {{ width: 18px; height: 12px; border: 1.5px solid; border-radius: 3px; display: inline-block; }}
  .lg b.ln {{ width: 26px; height: 0; border-top: 2px solid #4b5563; display: inline-block; }}
  .lg b.ln.branch {{ border-top-color: #b45309; }}
  .lg b.ln.return {{ border-top: 2px dashed #2563eb; }}
  .wrap {{ overflow-x: auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; }}
  svg {{ display: block; min-width: {W}px; width: 100%; height: auto; }}
  .stage.s0 {{ fill: #f1f5f9; }} .stage.s1 {{ fill: #eef2ff; }}
  .stage-label {{ font-size: 12px; fill: #475569; text-anchor: middle; font-weight: 600; letter-spacing: .02em; }}
  .lane {{ fill: transparent; stroke: #e2e8f0; }} .lane.l1 {{ fill: rgba(148,163,184,.06); }}
  .lane-label {{ font-weight: 600; fill: #334155; text-anchor: middle; }}
  .lane-sep {{ stroke: #cbd5e1; }}
  .edge {{ fill: none; stroke: #4b5563; stroke-width: 1.5; }}
  .edge.branch {{ stroke: #b45309; }}
  .edge.return {{ stroke: #2563eb; stroke-dasharray: 5 4; }}
  .elabel rect {{ fill: #fff; stroke: #e5e7eb; }}
  .elabel text {{ font-size: 11px; fill: #374151; text-anchor: middle; }}
  .elabel.branch text {{ fill: #92400e; }} .elabel.return text {{ fill: #1d4ed8; }}
  .node rect {{ stroke-width: 1.8; }}
  .node:hover rect {{ stroke-width: 3; }}
    .nlabel {{ font-weight: 600; text-anchor: middle; }}
  .nsub {{ text-anchor: middle; opacity: .85; }}
  .card {{ font-size: 10px; font-weight: 700; text-anchor: end; }}
  .tag {{ fill: #1f2937; }} .tagt {{ font-size: 10px; fill: #fff; text-anchor: middle; }}
  ul {{ font-size: 13px; color: #374151; padding-left: 20px; }}
</style>
</head>
<body>
<h1>{esc(SRC['title'][lang])}</h1>
<div class="meta">{esc(SRC['based_on'][lang])} · {esc(SRC['version'])}</div>
<div class="legend">{legend}</div>
<div class="wrap">
{''.join(svg)}
</div>
<ul>{notes}</ul>
</body>
</html>
"""


for lang in ("zh", "en"):
    (OUT / f"pipeline_flow.{lang}.html").write_text(render(lang), encoding="utf-8")
    print(f"wrote docs/status/pipeline_flow.{lang}.html")
