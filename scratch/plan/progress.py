"""Task 10 section 2: progress numbers, pipeline spend and forecast, Claude Code session usage.

Data: docs/status/progress.yaml (one row per Must task of the 2026-11-05 plan) and
docs/autorun/budget_ledger.jsonl (pipeline model calls). Output: docs/status/progress.zh.md and the
fixed header block that opens every stop report.

  uv run python scratch/plan/progress.py                     print the header block
  uv run python scratch/plan/progress.py --write             also regenerate docs/status/progress.zh.md
  uv run python scratch/plan/progress.py --cc-session <session.jsonl> [--write]
                                                             add Claude Code's own usage for that session

Arithmetic
  hours median      = midpoint of the plan's range
  workload %        = hours of tasks whose status is 已做待验收 or 已验收 / all hours
  completion %      = sum(hours x credit) / all hours, credit 已验收 1.0, 已做待验收 0.7, 未做 0
  forecast          = sum(records x measured cost per record) x (1 + margin)

Token rules (owner's accounting rules): the four token classes are always listed separately, cache
writes split by TTL, never an equal-weight total. Dollar figures weight each class by the official API
list price of its model (`src/freight_lineitems/budget.py` PRICES) and are a proxy, not a bill. A model
that is not in PRICES gets token counts only.
Session transcripts: one message appears on several lines while it streams; lines are grouped by
`message.id` and only the LAST usage is kept. Subagent transcripts in `<session-id>/subagents/agent-*.jsonl`
are included.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/status/progress.yaml"
OUT = ROOT / "docs/status/progress.zh.md"
DONE = ("已做待验收", "已验收")
STATUSES = ("未做", "已做待验收", "已验收")
OWNERS = ("CC", "人工")
CLASSES = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
CLASS_ZH = {"input": "input", "output": "output", "cache_write_5m": "cache write 5m",
            "cache_write_1h": "cache write 1h", "cache_read": "cache read"}
PROXY = "API 价格代理值，非实际账单"
NEED_METER = "需从 Tiny Meter 读取"


def load_prices() -> dict:
    """PRICES from src/freight_lineitems/budget.py, loaded by path (no package install needed)."""
    spec = importlib.util.spec_from_file_location("_fl_budget", ROOT / "src/freight_lineitems/budget.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod   # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod.PRICES


# ---------- progress arithmetic ----------

def median_hours(task: dict) -> float:
    lo, hi = task["hours"]
    return (lo + hi) / 2


def validate(tasks: list[dict]) -> None:
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    for t in tasks:
        if t["status"] not in STATUSES:
            raise ValueError(f"{t['id']}: unknown status {t['status']!r}")
        if t["owner"] not in OWNERS:
            raise ValueError(f"{t['id']}: unknown owner {t['owner']!r}")
        lo, hi = t["hours"]
        if not 0 < lo <= hi:
            raise ValueError(f"{t['id']}: bad hours {t['hours']}")


def summarize(tasks: list[dict], credit: dict) -> dict:
    """Totals for all tasks and split by owner. Percentages are None when a group has no hours."""
    def one(group: list[dict]) -> dict:
        total = sum(median_hours(t) for t in group)
        done = sum(median_hours(t) for t in group if t["status"] in DONE)
        earned = sum(median_hours(t) * credit[t["status"]] for t in group)
        return {
            "n": len(group), "hours": total, "done_hours": done, "earned_hours": earned,
            "n_by_status": {s: sum(1 for t in group if t["status"] == s) for s in STATUSES},
            "workload_pct": 100 * done / total if total else None,
            "completion_pct": 100 * earned / total if total else None,
        }
    out = {"all": one(tasks)}
    for o in OWNERS:
        out[o] = one([t for t in tasks if t["owner"] == o])
    return out


def with_assumed_done(tasks: list[dict], ids: list[str]) -> list[dict]:
    """Copy of tasks where the named 未做 tasks become 已做待验收 (next-leg assumption)."""
    known = {t["id"] for t in tasks}
    missing = [i for i in ids if i not in known]
    if missing:
        raise ValueError(f"next_leg.assume_done names unknown tasks: {missing}")
    return [{**t, "status": "已做待验收"} if t["id"] in ids and t["status"] == "未做" else t for t in tasks]


# ---------- pipeline ledger ----------

def read_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def split_legs(entries: list[dict], leg1_last_run_contains: str) -> tuple[list[dict], list[dict]]:
    """Leg 1 = entries up to and including the LAST one whose run name contains the marker (file order)."""
    idx = [i for i, e in enumerate(entries) if leg1_last_run_contains in e["run"]]
    if not idx:
        raise ValueError(f"no ledger entry contains {leg1_last_run_contains!r}")
    cut = idx[-1] + 1
    return entries[:cut], entries[cut:]


def ledger_totals(entries: list[dict], prices: dict) -> dict:
    tok = {c: 0 for c in CLASSES}
    calls = 0
    recomputed = 0.0
    unpriced = set()
    for e in entries:
        for u in e.get("usage", []):
            calls += u.get("n_calls", 0)
            for c in CLASSES:
                tok[c] += u.get(c, 0)
            p = prices.get(u["model"])
            if p is None:
                unpriced.add(u["model"])
            else:
                recomputed += sum(u.get(c, 0) * p[c] for c in CLASSES) / 1e6
    starts = [e["started_at"] for e in entries if e.get("started_at")]
    ends = [e["finished_at"] for e in entries if e.get("finished_at")]
    return {
        "runs": len(entries), "records": sum(e.get("n_records") or 0 for e in entries), "calls": calls,
        "tokens": tok, "cost_usd": sum(e.get("cost_usd") or 0 for e in entries),
        "cost_recomputed_usd": recomputed, "unpriced_models": sorted(unpriced),
        "first": min(starts) if starts else None, "last": max(ends) if ends else None,
    }


def rate_per_record(entries: list[dict], run_markers: list[str]) -> dict:
    """Measured cost per record over the ledger entries whose run name contains any marker."""
    sel = [e for e in entries if any(m in e["run"] for m in run_markers)]
    recs = sum(e.get("n_records") or 0 for e in sel)
    cost = sum(e.get("cost_usd") or 0 for e in sel)
    if not sel or not recs:
        raise ValueError(f"no ledger entries with records for {run_markers}")
    return {"runs": [e["run"] for e in sel], "records": recs, "cost_usd": cost, "per_record": cost / recs}


def forecast(items: list[dict], rates: dict, margin: float) -> dict:
    """Each item: records x rate. Totals per `when` (next / later), optional items kept apart; margin on top."""
    rows = []
    for it in items:
        base = it["records"] * rates[it["rate"]]["per_record"]
        rows.append({**it, "base_usd": base, "with_margin_usd": base * (1 + margin)})

    def total(when: str, optional: bool) -> float:
        return sum(r["with_margin_usd"] for r in rows if r["when"] == when and bool(r.get("optional")) == optional)
    return {"rows": rows, "next": total("next", False), "next_optional": total("next", True),
            "later": total("later", False), "later_optional": total("later", True)}


# ---------- Claude Code session ----------

def session_files(session: Path) -> tuple[Path, list[Path]]:
    sub = session.with_suffix("") / "subagents"
    return session, sorted(sub.glob("agent-*.jsonl")) if sub.is_dir() else []


def read_usage(path: Path) -> dict:
    """message.id -> (timestamp, model, usage) for one transcript; a later line for the same id replaces
    the earlier one, so the last usage wins."""
    last: dict[str, tuple] = {}
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            m = o.get("message") if isinstance(o, dict) else None
            if not isinstance(m, dict) or not isinstance(m.get("usage"), dict) or not m.get("id"):
                continue
            last[m["id"]] = (o.get("timestamp"), m.get("model") or "unknown", m["usage"])
    return last


def tally(messages: dict) -> dict:
    """Per model: message count and token classes. Cache writes are split by TTL from `cache_creation`;
    when a message only has the flat `cache_creation_input_tokens`, those tokens go to `cache_write_ttl_unknown`
    (never guessed). `flat_mismatch` counts messages whose flat field differs from the TTL sum."""
    by_model: dict[str, dict] = {}
    stamps = []
    for ts, model, u in messages.values():
        if model == "<synthetic>":
            continue
        d = by_model.setdefault(model, {"messages": 0, **{c: 0 for c in CLASSES},
                                        "cache_write_ttl_unknown": 0, "flat_mismatch": 0})
        d["messages"] += 1
        d["input"] += u.get("input_tokens") or 0
        d["output"] += u.get("output_tokens") or 0
        d["cache_read"] += u.get("cache_read_input_tokens") or 0
        flat = u.get("cache_creation_input_tokens") or 0
        cc = u.get("cache_creation")
        if isinstance(cc, dict):
            w5 = cc.get("ephemeral_5m_input_tokens") or 0
            w1 = cc.get("ephemeral_1h_input_tokens") or 0
            d["cache_write_5m"] += w5
            d["cache_write_1h"] += w1
            if flat != w5 + w1:
                d["flat_mismatch"] += 1
        else:
            d["cache_write_ttl_unknown"] += flat
        if ts:
            stamps.append(ts)
    return {"by_model": by_model, "first": min(stamps) if stamps else None, "last": max(stamps) if stamps else None}


def proxy_usd(model_tokens: dict, price: dict | None) -> float | None:
    """API list-price proxy for one model; None when the model has no price or has cache writes of unknown TTL."""
    if price is None or model_tokens.get("cache_write_ttl_unknown"):
        return None
    return sum(model_tokens[c] * price[c] for c in CLASSES) / 1e6


def cc_session(session: Path, prices: dict) -> dict | None:
    """Usage of one Claude Code session incl. subagents; None when the transcript cannot be read."""
    try:
        main, subs = session_files(session)
        main_msgs = read_usage(main)
        sub_msgs: dict = {}
        for p in subs:
            sub_msgs.update(read_usage(p))
    except OSError:
        return None
    sub_msgs = {k: v for k, v in sub_msgs.items() if k not in main_msgs}   # an id is counted once
    both = {**main_msgs, **sub_msgs}
    out = {"session": session.name, "n_subagent_files": len(subs),
           "main": tally(main_msgs), "subagents": tally(sub_msgs), "all": tally(both)}
    for part in ("main", "subagents", "all"):
        for model, d in out[part]["by_model"].items():
            d["proxy_usd"] = proxy_usd(d, prices.get(model))
    return out


# ---------- rendering ----------

def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.1f}%"


def h(x: float) -> str:
    return f"{x:g}"


def n(x: int) -> str:
    return f"{x:,}"


def usd(x: float) -> str:
    return f"${x:,.2f}"


def build(data: dict, ledger_entries: list[dict], prices: dict, session: dict | None, session_asked: bool) -> dict:
    tasks = data["tasks"]
    validate(tasks)
    credit = data["meta"]["credit"]
    now = summarize(tasks, credit)
    nxt = summarize(with_assumed_done(tasks, data["next_leg"]["assume_done"]), credit)
    lg = data["ledger"]
    leg1, leg2 = split_legs(ledger_entries, lg["leg1_last_run_contains"])
    rates = {k: {**rate_per_record(ledger_entries, v["runs"]), "note": v["note"]} for k, v in lg["rates"].items()}
    fc = forecast(lg["forecast"], rates, lg["margin"])
    return {"data": data, "now": now, "next": nxt, "leg1": ledger_totals(leg1, prices),
            "leg2": ledger_totals(leg2, prices), "total": ledger_totals(ledger_entries, prices),
            "rates": rates, "forecast": fc, "session": session, "session_asked": session_asked}


def header_block(r: dict) -> str:
    d, now, nxt, fc = r["data"], r["now"], r["next"], r["forecast"]
    a, cc, hm = now["all"], now["CC"], now["人工"]
    spent = r["total"]["cost_usd"]
    lines = [
        f"1. CC 与人工的划分：Must 共 {a['n']} 项、{h(a['hours'])} 人时（工时中值）。CC {cc['n']} 项 {h(cc['hours'])} 人时，"
        f"人工 {hm['n']} 项 {h(hm['hours'])} 人时。",
        f"2. 工作量：{pct(a['workload_pct'])}（已做 {h(a['done_hours'])} / {h(a['hours'])} 人时）。"
        f"CC {pct(cc['workload_pct'])}，人工 {pct(hm['workload_pct'])}。",
        f"3. 完成度：{pct(a['completion_pct'])}（已验收算 100%，已做待验收算 70%；现在已验收 {a['n_by_status']['已验收']} 项、"
        f"已做待验收 {a['n_by_status']['已做待验收']} 项、未做 {a['n_by_status']['未做']} 项）。"
        f"CC {pct(cc['completion_pct'])}，人工 {pct(hm['completion_pct'])}。",
        "4. 需要你处理的事：",
        *[f"   - {x}" for x in d["owner_actions"]],
        f"5. 下一段（{d['next_leg']['name']}）预计：工作量 {pct(a['workload_pct'])} → {pct(nxt['all']['workload_pct'])}，"
        f"完成度 {pct(a['completion_pct'])} → {pct(nxt['all']['completion_pct'])}。"
        f"假设做完：{'、'.join(d['next_leg']['assume_done'])}。{d['next_leg']['note']}",
        f"6. 花费（管道调模型，{PROXY}）：已用 {usd(spent)}（第一段 {usd(r['leg1']['cost_usd'])}，第二段 {usd(r['leg2']['cost_usd'])}）。"
        f"下一段预计 {usd(fc['next'])}（含 {int(d['ledger']['margin'] * 100)}% 调试余量；选做项另加 {usd(fc['next_optional'])}）；"
        f"之后到项目结束再加 {usd(fc['later'])}；全项目预计 {usd(spent + fc['next'] + fc['later'])}"
        f"（选做项都做则 {usd(spent + fc['next'] + fc['next_optional'] + fc['later'] + fc['later_optional'])}）。",
    ]
    return "\n".join(lines)


def token_table(rows: list[tuple[str, dict]]) -> list[str]:
    out = ["| | 运行次数 | 记录条次 | 模型调用 | input | output | cache write 5m | cache write 1h | cache read | 金额 | 时间窗口（UTC） |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, t in rows:
        k = t["tokens"]
        out.append(f"| {name} | {t['runs']} | {n(t['records'])} | {n(t['calls'])} | {n(k['input'])} | {n(k['output'])} | "
                   f"{n(k['cache_write_5m'])} | {n(k['cache_write_1h'])} | {n(k['cache_read'])} | {usd(t['cost_usd'])} | "
                   f"{t['first']} 到 {t['last']} |")
    return out


def session_section(r: dict) -> list[str]:
    s = r["session"]
    out = ["## 5. Claude Code 自己这个会话的消耗", ""]
    if s is None:
        out.append(NEED_METER + ("（给出的会话文件读不到）。" if r["session_asked"] else
                                 "（生成本文件时没有给 `--cc-session`）。"))
        return out
    out += [f"会话文件：`{s['session']}`，另有 {s['n_subagent_files']} 个子代理记录（`<会话编号>/subagents/agent-*.jsonl`）一并计入。",
            f"时间窗口（UTC）：{s['all']['first']} 到 {s['all']['last']}。不同时间窗口的结果不能直接比较。",
            "口径：按 `message.id` 去重，同一条消息只取最后一行的 usage；四类 token 分开列，缓存写入按 TTL 分开，不给等权合计。", "",
            "| 范围 | 模型 | 消息数 | input | output | cache write 5m | cache write 1h | cache read | " + PROXY + " |",
            "|---|---|---|---|---|---|---|---|---|"]
    notes = set()
    for part, zh in (("main", "主会话"), ("subagents", "子代理"), ("all", "合计")):
        for model, d in sorted(s[part]["by_model"].items()):
            if d["proxy_usd"] is None:
                money = "只列 token"
                notes.add(model)
            else:
                money = usd(d["proxy_usd"])
            out.append(f"| {zh} | `{model}` | {n(d['messages'])} | {n(d['input'])} | {n(d['output'])} | {n(d['cache_write_5m'])} | "
                       f"{n(d['cache_write_1h'])} | {n(d['cache_read'])} | {money} |")
    out.append("")
    for model in sorted(notes):
        out.append(f"- `{model}`：`src/freight_lineitems/budget.py` 的 `PRICES` 里没有这个模型的单价（或有 TTL 不明的缓存写入），只列 token 数，不折算金额。")
    unknown = sum(d["cache_write_ttl_unknown"] for d in s["all"]["by_model"].values())
    mism = sum(d["flat_mismatch"] for d in s["all"]["by_model"].values())
    out.append(f"- 交叉校验：扁平字段 `cache_creation_input_tokens` 与两种 TTL 之和不相等的消息 {mism} 条；没有 TTL 明细、无法归类的缓存写入 {n(unknown)} token。")
    out.append("- 订阅模式下没有按这个数扣费；它只用于量级比较，不等于配额消耗。")
    return out


def render(r: dict) -> str:
    d, now, fc = r["data"], r["now"], r["forecast"]
    m = d["meta"]
    out = ["<!-- 由 scratch/plan/progress.py 从 docs/status/progress.yaml 和账本生成，不要手改 -->",
           "# 进度、花费和预计", "",
           f"> 由 `scratch/plan/progress.py` 生成，数据在 [`progress.yaml`](progress.yaml)。最后更新：{m['updated']}。"
           f"计划：`{m['plan']}` 第 3 节的 23 项“必须做”。", "",
           "## 1. 停点汇报开头的几行", "", header_block(r), "",
           "## 2. 怎么算的", "",
           "- **工时中值**：计划里人时区间的中点。",
           "- **工作量 %** = 已做任务（已做待验收、已验收）的工时 ÷ 全部工时。",
           "- **完成度 %** = Σ(工时 × 系数) ÷ 全部工时，系数：已验收 1.0，已做待验收 0.7，未做 0。",
           f"- **负责方**：{m['owner_rule']}",
           f"- **状态**：{m['status_rule']}", "",
           "| | 项数 | 工时中值 | 已做工时 | 工作量 % | 完成度 % | 已验收 / 已做待验收 / 未做 |", "|---|---|---|---|---|---|---|"]
    for key, zh in (("all", "全部"), ("CC", "CC"), ("人工", "人工")):
        s = now[key]
        b = s["n_by_status"]
        out.append(f"| {zh} | {s['n']} | {h(s['hours'])} | {h(s['done_hours'])} | {pct(s['workload_pct'])} | {pct(s['completion_pct'])} | "
                   f"{b['已验收']} / {b['已做待验收']} / {b['未做']} |")
    pm = {"cc": [t for t in d["tasks"] if t["plan_mode"] == "cc"], "human": [t for t in d["tasks"] if t["plan_mode"] == "human"]}
    out += ["", f"按计划 5.1 原来的口径（不看实际由谁做）：写代码为主 {len(pm['cc'])} 项 {h(sum(map(median_hours, pm['cc'])))} 人时，"
                f"按人工估 {len(pm['human'])} 项 {h(sum(map(median_hours, pm['human'])))} 人时。", "",
            "## 3. 每个 Must 任务", "",
            "| 编号 | 任务 | 人时区间 | 工时中值 | 负责方 | 状态 | 哪一段 | 为什么是这个状态 |", "|---|---|---|---|---|---|---|---|"]
    for t in d["tasks"]:
        owner = t["owner"] + ("（计划按人工估）" if t["owner"] == "CC" and t["plan_mode"] == "human" else "")
        out.append(f"| {t['id']} | {t['name']['zh']} | {t['hours'][0]}–{t['hours'][1]} | {h(median_hours(t))} | {owner} | {t['status']} | "
                   f"{t.get('leg', '—')} | {t['why']} |")
    lg = d["ledger"]
    out += ["", "## 4. 管道调模型的 token 和花费", "",
            f"来源：`{lg['path']}`（每次运行一行）。金额按 `src/freight_lineitems/budget.py` 的官方单价折算，是 **{PROXY}**。"
            f"第一段 = 账本里到 `{lg['leg1_last_run_contains']}` 为止（含）的各行，第二段 = 之后的各行。四类 token 分开列，缓存写入按 TTL 分开，不给等权合计。", ""]
    out += token_table([("第一段", r["leg1"]), ("第二段", r["leg2"]), ("合计", r["total"])])
    diff = abs(r["total"]["cost_usd"] - r["total"]["cost_recomputed_usd"])
    out += ["", f"核对：按单价从 token 数重算的合计是 {usd(r['total']['cost_recomputed_usd'])}，与账本里各行金额之和相差 {usd(diff)}。"
            + (f" 没有单价的模型：{r['total']['unpriced_models']}。" if r["total"]["unpriced_models"] else ""),
            "", "### 每条花费（实测）", "", "| 口径 | 取自哪些运行 | 条数 | 金额 | 每条 |", "|---|---|---|---|---|"]
    for k, v in r["rates"].items():
        out.append(f"| `{k}`：{v['note']} | {'、'.join('`' + x + '`' for x in v['runs'])} | {n(v['records'])} | {usd(v['cost_usd'])} | ${v['per_record']:.4f} |")
    mg = int(lg["margin"] * 100)
    out += ["", "### 预计", "",
            f"做法：假设的运行条数 × 实测每条花费，再加 {mg}% 的调试余量（重跑、中途失败、调试用的小样本）。假设的运行写在 `progress.yaml` 的 `ledger.forecast`，改了重新生成即可。", "",
            f"| 什么时候 | 假设的运行 | 条数 | 每条口径 | 不含余量 | 含 {mg}% 余量 |", "|---|---|---|---|---|---|"]
    for row in fc["rows"]:
        when = ("下一段" if row["when"] == "next" else "之后") + ("（选做）" if row.get("optional") else "")
        out.append(f"| {when} | {row['name']} | {n(row['records'])} | `{row['rate']}` | {usd(row['base_usd'])} | {usd(row['with_margin_usd'])} |")
    spent = r["total"]["cost_usd"]
    out += ["", f"- 下一段预计：{usd(fc['next'])}；选做项另加 {usd(fc['next_optional'])}。",
            f"- 之后到项目结束：{usd(fc['later'])}。",
            f"- 全项目预计：已用 {usd(spent)} + 下一段 {usd(fc['next'])} + 之后 {usd(fc['later'])} = {usd(spent + fc['next'] + fc['later'])}"
            f"（选做项都做则 {usd(spent + fc['next'] + fc['next_optional'] + fc['later'] + fc['later_optional'])}）。", ""]
    out += session_section(r)
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="regenerate docs/status/progress.zh.md")
    ap.add_argument("--cc-session", type=Path, help="path to a Claude Code session .jsonl (read-only)")
    args = ap.parse_args(argv)
    data = yaml.safe_load(DATA.read_text(encoding="utf-8"))
    prices = load_prices()
    session = cc_session(args.cc_session, prices) if args.cc_session else None
    r = build(data, read_ledger(ROOT / data["ledger"]["path"]), prices, session, bool(args.cc_session))
    print(header_block(r))
    if args.cc_session:
        print()
        print("\n".join(session_section(r)))
    if args.write:
        OUT.write_text(render(r), encoding="utf-8")
        print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
