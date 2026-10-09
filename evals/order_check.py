"""How the order of sessions within a day moves the evidence (ADR 0004).

ADR 0004 replays each day's sessions in clock order and rejects the list order
(its option B). This script prints the figures behind that choice, on the
knowledge-update questions that ADR 0005 admits:

1.  evidence sessions on the last day of each history, last of the day in
    either order, against chance;
1b. the latest evidence session on its own day, whatever day that is;
1c. every evidence session that shares its day: first and last of the day;
2.  the questions where the budget-filling baseline reaches evidence in one
    order and not the other, written out in full to a git-ignored file.

Both orders ask the question at 23:59 on its day. The rules, the pool and the
replay come from verify_adr_numbers.py, so they cannot drift apart.

    .venv/bin/python evals/order_check.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.verify_adr_numbers import (  # noqa: E402
    KU, NO_WINDOW, ROOT, build_records, day_of, evidence_sessions, load, pool_of, recall,
    replay_order, when,
)

OUT = ROOT / "data" / "longmemeval" / "order_check.md"


def fill(x: dict, order: str) -> tuple[set[int], bool]:
    """Sessions with a turn in the budget fill, and whether evidence reached it."""
    records, ends, evidence = build_records(x, order)
    sources = recall(x, records, ends, NO_WINDOW).sources
    by_id = {}
    for i in replay_order(x, order):
        for j in range(len(x["haystack_sessions"][i])):
            by_id[f"{x['haystack_session_ids'][i]}:{j}"] = i
    return {by_id[s] for s in sources}, bool(set(sources) & evidence)


def same_day(x: dict, i: int, order: str) -> list[int]:
    d = x["haystack_dates"]
    return [k for k in replay_order(x, order) if day_of(d[k]) == day_of(d[i])]


def main() -> int:
    _, data = load()
    pool = [x for x in pool_of(data) if x["question_type"] == KU]
    print(f"knowledge-update questions in the pool of ADR 0005: {len(pool)}")

    # -- 1 --------------------------------------------------------------------
    c = Counter()
    chance = 0.0
    for x in pool:
        d = x["haystack_dates"]
        written = replay_order(x, "clock")
        last_day = max(day_of(d[i]) for i in written)
        c["last day is the question's day"] += last_day == day_of(x["question_date"])
        on_last = [i for i in evidence_sessions(x) if day_of(d[i]) == last_day]
        c["questions with evidence on the last day"] += bool(on_last)
        for e in on_last:
            if len(same_day(x, e, "clock")) == 1:
                c["evidence sessions alone on the last day"] += 1
                continue
            c["evidence sessions sharing the last day"] += 1
            chance += 1 / len(same_day(x, e, "clock"))
            c["  last of the day, clock order"] += same_day(x, e, "clock")[-1] == e
            c["  last of the day, list order"] += same_day(x, e, "list")[-1] == e
    print("\nCHECK 1  evidence sessions on the last day of the history")
    for k in ("last day is the question's day", "questions with evidence on the last day",
              "evidence sessions alone on the last day", "evidence sessions sharing the last day",
              "  last of the day, clock order", "  last of the day, list order"):
        print(f"  {k:48s} {c[k]}")
    print(f"  {'  expected by chance':48s} {chance:.1f}")

    # -- 1b -------------------------------------------------------------------
    b = Counter()
    chance = 0.0
    for x in pool:
        latest = max(evidence_sessions(x), key=replay_order(x, "clock").index)
        day = same_day(x, latest, "clock")
        if len(day) == 1:
            b["alone on its day"] += 1
            continue
        b["sharing its day"] += 1
        chance += 1 / len(day)
        b["  last of its day, clock order"] += day[-1] == latest
        b["  last of its day, list order"] += same_day(x, latest, "list")[-1] == latest
    print("\nCHECK 1b  the latest evidence session, on its own day")
    for k in ("alone on its day", "sharing its day", "  last of its day, clock order", "  last of its day, list order"):
        print(f"  {k:48s} {b[k]}")
    print(f"  {'  expected by chance':48s} {chance:.1f}")

    # -- 1c -------------------------------------------------------------------
    e = Counter()
    chance = 0.0
    for x in pool:
        for i in evidence_sessions(x):
            day = same_day(x, i, "clock")
            if len(day) == 1:
                continue
            e["evidence sessions sharing their day"] += 1
            chance += 1 / len(day)
            for order in ("clock", "list"):
                o = same_day(x, i, order)
                e[f"  first of the day, {order} order"] += o[0] == i
                e[f"  last of the day, {order} order"] += o[-1] == i
    print("\nCHECK 1c  every evidence session that shares its day")
    for k in ("evidence sessions sharing their day", "  first of the day, clock order", "  first of the day, list order",
              "  last of the day, clock order", "  last of the day, list order"):
        print(f"  {k:48s} {e[k]}")
    print(f"  {'  expected by chance, first or last each':48s} {chance:.1f}")

    # -- 2 --------------------------------------------------------------------
    reach = {x["question_id"]: {o: fill(x, o) for o in ("clock", "list")} for x in pool}
    only_list = [q for q, r in reach.items() if r["list"][1] and not r["clock"][1]]
    only_clock = [q for q, r in reach.items() if r["clock"][1] and not r["list"][1]]
    print("\nCHECK 2  baseline reach by order")
    print(f"  reached in clock order: {sum(r['clock'][1] for r in reach.values())}")
    print(f"  reached in list order:  {sum(r['list'][1] for r in reach.values())}")
    print(f"  reached only in list order:  {len(only_list)} {only_list}")
    print(f"  reached only in clock order: {len(only_clock)} {only_clock}")
    x618 = next(x for x in data if x["question_id"] == "618f13b2")
    print(f"  618f13b2, outside the pool, in list order: reached = {fill(x618, 'list')[1]}")

    by_id = {x["question_id"]: x for x in pool}
    lines = ["# Order check: questions reached in one order only", "",
             "Generated by evals/order_check.py. `clock` sorts on the full timestamp (ADR 0004);",
             "`list` sorts on the day and keeps the list order within it (its option B). The question",
             "is asked at 23:59 on its day in both. `fill` marks a session with at least one turn",
             "in the baseline's 8000-token fill. Every day either fill reaches is shown, since the",
             "evidence is not always on the last day. Evidence turns are printed in full.", ""]
    for qid in only_list + only_clock:
        x = by_id[qid]
        d = x["haystack_dates"]
        ev = set(evidence_sessions(x))
        days = sorted({day_of(d[i]) for o in ("clock", "list") for i in reach[qid][o][0]})
        lines += [f"## {qid} — reached only in {'list' if qid in only_list else 'clock'} order", "",
                  f"- question: {x['question']}", f"- answer: {x['answer']}",
                  f"- question_date: {x['question_date']}",
                  f"- days either fill reaches: {', '.join(str(v) for v in days)}", ""]
        for order in ("clock", "list"):
            lines += [f"Days the fills reach, {order} order, earliest first:", "",
                      "| # | session | date | time | list position | evidence | fill |",
                      "|---|---|---|---|---|---|---|"]
            shown = [i for i in replay_order(x, order) if day_of(d[i]) in days]
            for n, i in enumerate(shown, start=1):
                lines.append(f"| {n} | {x['haystack_session_ids'][i]} | {day_of(d[i])} | "
                             f"{when(d[i]).strftime('%H:%M')} | {i} | {'yes' if i in ev else ''} | "
                             f"{'yes' if i in reach[qid][order][0] else ''} |")
            lines.append("")
        lines += ["Evidence turns, by list position:", ""]
        for i in sorted(ev):
            for j, t in enumerate(x["haystack_sessions"][i]):
                if t.get("has_answer"):
                    fence = "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", t["content"])), default=0))
                    lines += [f"### {x['haystack_session_ids'][i]}:{j} — {d[i]}, list position {i}, {t['role']}", "",
                              fence + "text", t["content"], fence, ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
