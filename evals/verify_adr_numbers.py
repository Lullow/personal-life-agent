"""Recompute every number stated in docs/adr/0004–0009 from the dataset.

Each claim is found in the ADR text by a pattern, so the table shows the number
as the record states it today rather than as this script remembers it. If a
record is reworded and a pattern no longer matches, the row says so instead of
passing silently.

Not every number in those records can come from the dataset. Each row is marked
with what kind of claim it is:

* ``exact`` / ``approx`` / ``sets`` — recomputed here, from the dataset or the code;
* ``external`` — a commit, revision or price from outside the repo, which this
  script cannot check offline;
* ``estimate`` — arithmetic on assumptions, such as tokens per message.

The rules are the ones ADR 0004 and 0005 decide: sessions in clock order, the
question asked at 23:59 on its day, and the pool that 0005 admits. Other
scripts in evals/ import them from here, so the pool is defined once. The
baseline figures run the real ``RecentTurnsMemory`` with a tiktoken counter.
Turn text is never truncated anywhere in this script.

    .venv/bin/python evals/verify_adr_numbers.py            # the table
    .venv/bin/python evals/verify_adr_numbers.py --facts    # every computed figure
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tiktoken  # noqa: E402

from life_agent.agent.memory import (  # noqa: E402
    DEFAULT_BUDGET_TOKENS,
    DEFAULT_HISTORY_TURNS,
    MemoryRecord,
    RecentTurnsMemory,
    make_record_id,
)

DATASET = ROOT / "data" / "longmemeval" / "longmemeval_s_cleaned.json"
# ADR 0004: the harness refuses any other file. The table below checks this
# constant against the record's text.
DATASET_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
ADR_DIR = ROOT / "docs" / "adr"
SSU, KU = "single-session-user", "knowledge-update"
TYPES = (SSU, KU)
PILOT_PER_TYPE = 10  # ADR 0005: M1 takes the first 10 of each type
# RecentTurnsMemory cannot yet take max_turns=None (ADR 0007), so "no window"
# is a window no history can reach.
NO_WINDOW = 10**9
# The pattern ADR 0008 counts as "time-worded". A definition, not a fact.
TIME_WORDED = re.compile(
    r"\b(how long|how many (days|weeks|months|years)|when did|ago|since when|how old)\b",
    re.IGNORECASE,
)
WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
         "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


# -- the rules of ADR 0004 and 0005 ------------------------------------------

def when(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y/%m/%d (%a) %H:%M")


def day_of(stamp: str) -> date:
    return when(stamp).date()


def question_time(x: dict) -> datetime:
    """ADR 0004: a question is asked at the end of its day."""
    return datetime.combine(day_of(x["question_date"]), time(23, 59))


def evidence_sessions(x: dict) -> list[int]:
    """Session indices, in list order, holding at least one has_answer turn."""
    return [i for i, s in enumerate(x["haystack_sessions"])
            if any(t.get("has_answer") for t in s)]


def exclusion_reasons(x: dict) -> list[str]:
    """Why ADR 0005 leaves *x* out; empty when it is eligible."""
    if x["question_type"] not in TYPES:
        return ["other type"]
    reasons = []
    if x["question_id"].endswith("_abs"):
        reasons.append("abstention")
    ids = x["haystack_session_ids"]
    if len(set(ids)) != len(ids):
        reasons.append("repeated session id")
    ev = evidence_sessions(x)
    d = x["haystack_dates"]
    if not ev:
        reasons.append("no evidence")
    elif any(when(d[i]) > question_time(x) for i in ev):
        reasons.append("evidence after the question's day")
    if ev and sorted(ev, key=lambda i: when(d[i])) != ev:
        reasons.append("evidence order")
    return reasons


def replay_order(x: dict, order: str = "clock") -> list[int]:
    """Session indices written: "clock" is ADR 0004, "list" is its option B."""
    d = x["haystack_dates"]
    idx = [i for i in range(len(d)) if when(d[i]) <= question_time(x)]
    if order == "clock":
        return sorted(idx, key=lambda i: when(d[i]))  # stable
    return sorted(idx, key=lambda i: (day_of(d[i]), i))


def stamp(x: dict, i: int, order: str) -> datetime:
    d = when(x["haystack_dates"][i])
    return d if order == "clock" else datetime.combine(d.date(), time())


def build_records(x: dict, order: str = "clock") -> tuple[list[MemoryRecord], set[int], set[str]]:
    records: list[MemoryRecord] = []
    session_ends: set[int] = set()
    evidence: set[str] = set()
    for i in replay_order(x, order):
        sid = x["haystack_session_ids"][i]
        for j, turn in enumerate(x["haystack_sessions"][i]):
            rid = make_record_id(sid, j)
            records.append(MemoryRecord(id=rid, role=turn["role"], content=turn["content"],
                                        kind="message", at=stamp(x, i, order), session_id=sid))
            if turn.get("has_answer"):
                evidence.add(rid)
        session_ends.add(len(records))
    return records, session_ends, evidence


# -- tokens ------------------------------------------------------------------

class TiktokenCounter:
    """o200k_base, cached by text. Special-token strings count as plain text (ADR 0006)."""

    def __init__(self) -> None:
        self._enc = tiktoken.get_encoding("o200k_base")
        self._cache: dict[str, int] = {}

    def count(self, text: str) -> int:
        n = self._cache.get(text)
        if n is None:
            n = len(self._enc.encode(text, disallowed_special=()))
            self._cache[text] = n
        return n


COUNTER = TiktokenCounter()


def recall(x: dict, records: list[MemoryRecord], ends: set[int], max_turns: int):
    memory = RecentTurnsMemory(max_turns=max_turns, token_counter=COUNTER)
    for k, record in enumerate(records, start=1):
        memory.write(record)
        if k in ends:
            memory.end_session()
    return memory.retrieve(x["question"], at=question_time(x), budget_tokens=DEFAULT_BUDGET_TOKENS)


def load() -> tuple[bytes, list[dict]]:
    raw = DATASET.read_bytes()
    return raw, json.loads(raw)


def load_pinned() -> list[dict]:
    """The dataset, or SystemExit if it is not the file ADR 0004 pins."""
    raw = DATASET.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != DATASET_SHA256:
        raise SystemExit(f"{DATASET.name} has sha256 {digest}; ADR 0004 pins {DATASET_SHA256}")
    return json.loads(raw)


def pool_of(data: list[dict]) -> list[dict]:
    return [x for x in data if not exclusion_reasons(x)]


# -- facts -------------------------------------------------------------------

def compute_facts(raw: bytes, data: list[dict]) -> dict:
    f: dict = {"sha256": hashlib.sha256(raw).hexdigest()}
    both = [x for x in data if x["question_type"] in TYPES]
    by_type = {t: [x for x in both if x["question_type"] == t] for t in TYPES}
    non_abs = [x for x in both if not x["question_id"].endswith("_abs")]
    f["file SSU"], f["file KU"] = len(by_type[SSU]), len(by_type[KU])

    # Cross-check: the date strings sort chronologically as text, which is how
    # LongMemEval's own reader sorts them.
    for x in both:
        d = x["haystack_dates"]
        assert sorted(range(len(d)), key=lambda i: d[i]) == \
            sorted(range(len(d)), key=lambda i: when(d[i])), x["question_id"]

    def descents(x: dict, level: str) -> int:
        d = x["haystack_dates"]
        key = when if level == "clock" else day_of
        return sum(key(d[i]) < key(d[i - 1]) for i in range(1, len(d)))

    ku_desc = [descents(x, "clock") for x in by_type[KU]]
    f["KU out of clock order"] = sum(n > 0 for n in ku_desc)
    f["KU clock descents min"] = min(n for n in ku_desc if n > 0)
    f["KU clock descents max"] = max(ku_desc)
    f["histories going back across days"] = sum(descents(x, "day") > 0 for x in both)
    f["SSU in clock order"] = sum(descents(x, "clock") == 0 for x in by_type[SSU])

    late = [(x, [s for s in x["haystack_dates"] if when(s) > when(x["question_date"])]) for x in both]
    late = [(x, s) for x, s in late if s]
    gaps = [(when(s) - when(x["question_date"])).total_seconds() for x, ss in late for s in ss]
    f["questions with sessions after the question"] = len(late)
    f["...of which KU"] = sum(x["question_type"] == KU for x, _ in late)
    f["...of which abstention"] = sum(x["question_id"].endswith("_abs") for x, _ in late)
    f["sessions after the question"] = len(gaps)
    f["...min minutes after"] = round(min(gaps) / 60)
    f["...max hours after"] = round(max(gaps) / 3600)
    f["...all on the question day"] = all(day_of(s) == day_of(x["question_date"]) for x, ss in late for s in ss)
    f["sessions on a later day than the question"] = sum(
        day_of(s) > day_of(x["question_date"]) for x in both for s in x["haystack_dates"])

    within_day, cross_day_against = set(), 0
    for x in non_abs:
        d, ev = x["haystack_dates"], evidence_sessions(x)
        q = when(x["question_date"])
        for i in ev:
            if when(d[i]).date() == q.date() and when(d[i]) > q:
                within_day.add(x["question_id"])
        for n, a in enumerate(ev):
            for b in ev[n + 1:]:
                if when(d[a]) > when(d[b]):
                    if day_of(d[a]) == day_of(d[b]):
                        within_day.add(x["question_id"])
                    else:
                        cross_day_against += 1
    f["within-day contradictions of evidence"] = sorted(within_day)
    f["cross-day evidence pairs against the dates"] = cross_day_against

    dup: dict[str, str] = {}
    dups_are_filler = True
    for x in both:
        ids = x["haystack_session_ids"]
        for sid, n in Counter(ids).items():
            if n < 2:
                continue
            dup[x["question_id"]] = x["question_type"]
            pos = [i for i, s in enumerate(ids) if s == sid]
            dups_are_filler &= (n == 2
                                and all(x["haystack_sessions"][p] == x["haystack_sessions"][pos[0]] for p in pos)
                                and len({x["haystack_dates"][p] for p in pos}) == len(pos)
                                and not any(t.get("has_answer") for p in pos for t in x["haystack_sessions"][p]))
    f["repeated-id questions"] = dup
    f["repeats are filler copies"] = dups_are_filler

    f["abstention per type"] = {t: sum(x["question_id"].endswith("_abs") for x in by_type[t]) for t in TYPES}
    f["abstention without evidence"] = all(
        not evidence_sessions(x) for x in both if x["question_id"].endswith("_abs"))
    reasons = {x["question_id"]: exclusion_reasons(x) for x in both}
    f["evidence order mismatches"] = sorted(q for q, r in reasons.items()
                                            if "evidence order" in r and "abstention" not in r)
    f["defects"] = sorted(q for q, r in reasons.items() if r and "abstention" not in r)
    f["excluded for evidence after the question's day"] = sorted(
        q for q, r in reasons.items() if "evidence after the question's day" in r and "abstention" not in r)

    by_id = {x["question_id"]: x for x in data}
    x = by_id["2133c1b5"]
    upd = [when(x["haystack_dates"][i]) for i in evidence_sessions(x) if when(x["haystack_dates"][i]) > when(x["question_date"])]
    f["2133c1b5 update / question"] = (upd[0].strftime("%H:%M"), when(x["question_date"]).strftime("%H:%M"))
    f["2133c1b5 same day"] = len(upd) == 1 and upd[0].date() == day_of(x["question_date"])
    x = by_id["618f13b2"]
    st = {}
    for i in evidence_sessions(x):
        for t in x["haystack_sessions"][i]:
            if t.get("has_answer"):
                for w in ("four times", "six times"):
                    if w in t["content"].lower():
                        st[w] = when(x["haystack_dates"][i])
    f["618f13b2 four / six / answer"] = (st["four times"].strftime("%H:%M"), st["six times"].strftime("%H:%M"), str(x["answer"]))
    f["618f13b2 same day"] = st["four times"].date() == st["six times"].date()
    f["e66b632c question"] = by_id["e66b632c"]["question"]

    pool = pool_of(data)
    pool_by_type = {t: [x for x in pool if x["question_type"] == t] for t in TYPES}
    for t in TYPES:  # cross-check by subtraction from the named exclusions
        assert len(by_type[t]) - f["abstention per type"][t] - sum(
            x["question_id"] in f["defects"] for x in by_type[t]) == len(pool_by_type[t]), t
    f["pool SSU"], f["pool KU"], f["pool"] = len(pool_by_type[SSU]), len(pool_by_type[KU]), len(pool)
    f["2133c1b5 in pool"] = "2133c1b5" in {x["question_id"] for x in pool}
    f["e66b632c in pool"] = "e66b632c" in {x["question_id"] for x in pool}

    special = set(tiktoken.get_encoding("o200k_base").special_tokens_set)
    rows: dict[str, list[dict]] = {t: [] for t in TYPES}
    for x in pool:
        records, ends, evidence = build_records(x, "clock")
        assert len({r.id for r in records}) == len(records), x["question_id"]
        counts = [COUNTER.count(r.content) for r in records]
        window = recall(x, records, ends, DEFAULT_HISTORY_TURNS)
        fill = recall(x, records, ends, NO_WINDOW)
        k = max(i for i, r in enumerate(records) if r.id in evidence)
        row = dict(
            last20=sum(counts[-20:]),
            window_full=len(window.sources) == 2 * DEFAULT_HISTORY_TURNS,
            in_window=bool(set(window.sources) & evidence),
            fill_n=len(fill.sources),
            in_fill=bool(set(fill.sources) & evidence),
            over_budget=fill.tokens_used > DEFAULT_BUDGET_TOKENS,
            longterm=sum(counts[k + 1:]) > DEFAULT_BUDGET_TOKENS,
            max_msg=max(counts),
            newest=counts[-1],
            n_ev_turns=len(evidence),
            n_ev_sessions=len(evidence_sessions(x)),
            answer_is_int=isinstance(x["answer"], int),
            time_worded=bool(TIME_WORDED.search(x["question"])),
            special=sum(any(s in r.content for s in special) for r in records),
            after_clock=sum(when(s) > when(x["question_date"]) for s in x["haystack_dates"]),
            orders_equal=replay_order(x, "clock") == replay_order(x, "list"),
        )
        if row["time_worded"]:
            text = " ".join(t["content"] for s in x["haystack_sessions"] for t in s if t.get("has_answer"))
            row["answer_literal"] = str(x["answer"]).lower() in text.lower()
        if x["question_type"] == KU:
            lrec, lends, lev = build_records(x, "list")
            row["in_fill_list"] = bool(set(recall(x, lrec, lends, NO_WINDOW).sources) & lev)
            # Position test: the latest evidence session on its own day.
            d = x["haystack_dates"]
            ev = evidence_sessions(x)
            for order in ("clock", "list"):
                o = replay_order(x, order)
                latest = max(ev, key=o.index)
                day = [i for i in o if day_of(d[i]) == day_of(d[latest])]
                row[f"shares_day_{order}"] = len(day) > 1
                row[f"last_of_day_{order}"] = len(day) > 1 and day[-1] == latest
                row[f"chance_{order}"] = 1 / len(day) if len(day) > 1 else 0.0
        rows[x["question_type"]].append(row)

    col = lambda t, k: [r[k] for r in rows[t]]  # noqa: E731
    allr = rows[SSU] + rows[KU]
    a = lambda k: [r[k] for r in allr]  # noqa: E731
    f["last20 min / max"] = (min(a("last20")), max(a("last20")))
    f["last20 median SSU / KU"] = (statistics.median(col(SSU, "last20")), statistics.median(col(KU, "last20")))
    f["window returns 20 messages"] = sum(a("window_full"))
    f["fill min / max"] = (min(a("fill_n")), max(a("fill_n")))
    f["fill median SSU / KU / all"] = (statistics.median(col(SSU, "fill_n")), statistics.median(col(KU, "fill_n")),
                                       statistics.median(a("fill_n")))
    f["evidence in window SSU / KU"] = (sum(col(SSU, "in_window")), sum(col(KU, "in_window")))
    f["evidence in fill SSU / KU"] = (sum(col(SSU, "in_fill")), sum(col(KU, "in_fill")))
    f["KU evidence in fill, list order"] = sum(col(KU, "in_fill_list"))
    f["in fill exactly when not long-term"] = all(r["in_fill"] == (not r["longterm"]) for r in allr)
    f["largest message"] = max(a("max_msg"))
    f["newest message over budget"] = sum(n > DEFAULT_BUDGET_TOKENS for n in a("newest"))
    f["fill over budget"] = sum(a("over_budget"))
    f["integer answers"] = sum(a("answer_is_int"))
    f["time-worded"] = sum(a("time_worded"))
    f["time-worded answered literally"] = sum(r.get("answer_literal", False) for r in allr)
    f["SSU one evidence turn"] = sum(n == 1 for n in col(SSU, "n_ev_turns"))
    f["KU two turns in two sessions"] = sum(r["n_ev_turns"] == 2 and r["n_ev_sessions"] == 2 for r in rows[KU])
    f["min evidence turns"] = min(a("n_ev_turns"))
    f["KU evidence sessions per question"] = dict(sorted(Counter(col(KU, "n_ev_sessions")).items()))
    f["KU not exactly two evidence sessions"] = sum(n != 2 for n in col(KU, "n_ev_sessions"))
    f["special-token turns"] = sum(a("special"))
    f["sessions after the clock time, pool"] = sum(a("after_clock"))
    f["histories with them, pool"] = sum(n > 0 for n in a("after_clock"))
    f["SSU orders identical"] = all(col(SSU, "orders_equal"))
    f["KU latest evidence shares its day"] = sum(col(KU, "shares_day_clock"))
    f["KU latest evidence last of its day, clock / list"] = (sum(col(KU, "last_of_day_clock")),
                                                             sum(col(KU, "last_of_day_list")))
    f["KU latest evidence last of its day, chance"] = round(sum(col(KU, "chance_clock")), 1)
    f["KU latest evidence same day in both orders"] = col(KU, "shares_day_clock") == col(KU, "shares_day_list") \
        and col(KU, "chance_clock") == col(KU, "chance_list")
    return f


# -- claims ------------------------------------------------------------------

@dataclass
class Claim:
    adr: str
    label: str
    pattern: str
    computed: object = None     # tuple matched against the groups, or a bool
    kind: str = "exact"         # exact | approx | sets | external | estimate
    note: str = ""
    tolerance: float = 0.05
    groups: tuple = field(default=(), init=False)
    status: str = field(default="", init=False)


def norm(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).replace(",", "").strip()
    return WORDS.get(s.lower(), s)


def judge(claim: Claim, text: str) -> None:
    m = re.search(claim.pattern, text)
    if m is None:
        claim.status = "TEXT MISSING"
        return
    claim.groups = m.groups()
    if claim.kind in ("external", "estimate"):
        claim.status = claim.kind.upper()
        return
    if isinstance(claim.computed, bool):
        claim.status = "OK" if claim.computed else "DIFF"
        return
    stated = [norm(g) for g in claim.groups]
    if claim.kind == "sets":
        ok, start = True, 0
        for group in claim.computed:
            ok &= set(stated[start:start + len(group)]) == set(group)
            start += len(group)
        claim.status = "OK" if ok and start == len(stated) else "DIFF"
        return
    computed = [norm(c) for c in claim.computed]
    if claim.kind == "approx":
        ok = len(stated) == len(computed) and all(
            abs(float(s) - float(c)) <= claim.tolerance * max(abs(float(c)), 1e-9)
            for s, c in zip(stated, computed))
    else:
        ok = stated == computed
    claim.status = "OK" if ok else "DIFF"


def fmt(values: object) -> str:
    if isinstance(values, bool):
        return "true" if values else "false"
    if values is None:
        return "—"
    return " / ".join(str(v) for v in values)


def claims_for(f: dict) -> list[Claim]:
    ku_last_clock, ku_last_list = f["KU latest evidence last of its day, clock / list"]
    return [
        # 0004
        Claim("0004", "dataset sha256", r"sha256 `([0-9a-f]{64})`", (f["sha256"],)),
        Claim("0004", "the sha256 the harness pins", r"sha256 `([0-9a-f]{64})`", (DATASET_SHA256,),
              note="DATASET_SHA256 in this script"),
        Claim("0004", "HF revision", r"revision `([0-9a-f]{40})`", kind="external",
              note="HF API, checked in session 2026-09-26"),
        Claim("0004", "no session on a later day than its question",
              r"No session in either type is dated on a later day than its question",
              f["sessions on a later day than the question"] == 0),
        Claim("0004", "lists never go back across days",
              r"across days every history lists its sessions in date order",
              f["histories going back across days"] == 0, note="all 148 histories of the two types"),
        Claim("0004", "KU out of clock order within a day; min / max",
              r"[Aa]ll (\d+) `knowledge-update` histories list their sessions out of clock order within a day, between (\d+) and (\d+) times each",
              (f["KU out of clock order"], f["KU clock descents min"], f["KU clock descents max"]),
              note=f"of {f['file KU']} KU in the file"),
        Claim("0004", "SSU in clock order", r"the (\d+) `single-session-user` histories are in clock order",
              (f["SSU in clock order"],), note=f"of {f['file SSU']} SSU in the file"),
        Claim("0004", "questions / sessions after the question; minutes / hours",
              r"(\d+) `knowledge-update` questions, one of them an abstention question, have (\d+) sessions timed after the question, from (\d+) minutes? to (\d+) hours later, all on the question's own day",
              (f["...of which KU"], f["sessions after the question"], f["...min minutes after"], f["...max hours after"]),
              note=f"all KU: {f['...of which KU'] == f['questions with sessions after the question']}; "
                   f"abstention among them: {f['...of which abstention']}; "
                   f"all on the question's day: {f['...all on the question day']}"),
        Claim("0004", "within-day contradictions: 2133c1b5 and 618f13b2",
              r"Within a day the clock also contradicts the evidence, in two questions",
              f["within-day contradictions of evidence"] == ["2133c1b5", "618f13b2"],
              note=f"{f['within-day contradictions of evidence']}"),
        Claim("0004", "2133c1b5 update / question time", r"stated at (\d\d:\d\d) on a day the question is asked at (\d\d:\d\d)",
              f["2133c1b5 update / question"], note="same day" if f["2133c1b5 same day"] else "NOT the same day"),
        Claim("0004", "no cross-day contradiction of two evidence sessions",
              r"Across days, the dates never contradict the order of two evidence sessions",
              f["cross-day evidence pairs against the dates"] == 0),
        Claim("0004", "histories with a repeated session id", r"(\d+) histories contain the same session twice",
              (len(f["repeated-id questions"]),)),
        Claim("0004", "…identical, on different dates", r"identical in content, on different dates",
              f["repeats are filler copies"]),
        Claim("0004", "the at limit is inclusive", r"The limit is inclusive: a session timed 23:59 on the question's day is written and can be recalled",
              _inclusive_at_limit(), note="RecentTurnsMemory: a record at 23:59 is returned by retrieve(at=23:59)"),
        Claim("0004", "LongMemEval commit", r"commit `(d0c699fa[0-9a-f]{32})`", kind="external",
              note="GitHub, checked in session 2026-09-26"),
        Claim("0004", "position test pool", r"Counted on the (\d+) measured `knowledge-update` questions",
              (f["pool KU"],)),
        Claim("0004", "latest evidence last of its day: clock / sharing / chance / list",
              r"puts the latest evidence session last on its day in (\d+) of the (\d+) questions where that day holds other sessions, close to the ([\d.]+) expected by chance; the list order does so in (\d+)",
              (ku_last_clock, f["KU latest evidence shares its day"], f["KU latest evidence last of its day, chance"], ku_last_list),
              note="same day and chance in both orders" if f["KU latest evidence same day in both orders"]
              else "day or chance DIFFERS between orders"),
        Claim("0004", "rejected A: questions / sessions / histories",
              r"of the (\d+) questions measured under this record, it would remove (\d+) sessions from (\d+) histories",
              (f["pool"], f["sessions after the clock time, pool"], f["histories with them, pool"])),
        Claim("0004", "rejected B: questions / list reach / clock reach",
              r"on the same (\d+) questions the baseline would reach evidence in (\d+) instead of (\d+)",
              (f["pool KU"], f["KU evidence in fill, list order"], f["evidence in fill SSU / KU"][1])),
        Claim("0004", "consequence: clock reach / pool / list reach",
              r"(\d+) of (\d+) `knowledge-update` questions in clock order against (\d+) in list order",
              (f["evidence in fill SSU / KU"][1], f["pool KU"], f["KU evidence in fill, list order"])),
        # 0005
        Claim("0005", "SSU / KU in the file", r"holds (\d+) and (\d+) of them", (f["file SSU"], f["file KU"])),
        Claim("0005", "abstention per type", r"`_abs`: (\d+) of each type",
              (f["abstention per type"][SSU],) if f["abstention per type"][SSU] == f["abstention per type"][KU]
              else (str(f["abstention per type"]),)),
        Claim("0005", "abstention marks no evidence", r"They mark no evidence turns", f["abstention without evidence"]),
        Claim("0005", "repeated-id questions (SSU; KU)",
              r"`(\w{8})`, `(\w{8})` and `(\w{8})` \(`single-session-user`\), `(\w{8})` and `(\w{8})` \(`knowledge-update`\)",
              (tuple(sorted(q for q, t in f["repeated-id questions"].items() if t == SSU)),
               tuple(sorted(q for q, t in f["repeated-id questions"].items() if t == KU))),
              kind="sets", note="compared as sets per type"),
        Claim("0005", "repeats are filler, never evidence", r"In all five the repeat is a filler session, never evidence",
              f["repeats are filler copies"] and len(f["repeated-id questions"]) == 5),
        Claim("0005", "618f13b2 four / six / answer",
              r"\"Four times\" is dated (\d\d:\d\d) and \"six times\" (\d\d:\d\d) on the same day, and the answer is (\w+)",
              f["618f13b2 four / six / answer"], note="same day" if f["618f13b2 same day"] else "NOT the same day"),
        Claim("0005", "618f13b2 is the only order mismatch",
              r"It is the only question of the two types whose evidence sessions come in a different order by time than in the list",
              f["evidence order mismatches"] == ["618f13b2"], note=f"{f['evidence order mismatches']}"),
        Claim("0005", "2133c1b5 is measured", r"`2133c1b5`, whose updated value is timed hours after the question on the same day, is measured",
              f["2133c1b5 in pool"] and f["excluded for evidence after the question's day"] == []),
        Claim("0005", "eligible SSU / KU", r"That leaves \*\*(\d+) `single-session-user` and (\d+) `knowledge-update`\*\*",
              (f["pool SSU"], f["pool KU"]), note="cross-checked by subtraction"),
        Claim("0005", "pool caps", r"caps the comparison at (\d+) and (\d+) questions", (f["pool SSU"], f["pool KU"])),
        Claim("0005", "data-defect exclusions", r"the other (\w+) are data defects", (len(f["defects"]),),
              note=f"{f['defects']}"),
        # 0006
        Claim("0006", "budget constant", r"\*\*The budget is (\d+) tokens\*\* \(`DEFAULT_BUDGET_TOKENS`\)",
              (DEFAULT_BUDGET_TOKENS,), note="from life_agent/agent/memory.py"),
        Claim("0006", "gpt-4o tokenizer", r"tiktoken's `(\w+)`", (tiktoken.encoding_for_model("gpt-4o").name,),
              note="tiktoken.encoding_for_model('gpt-4o')"),
        Claim("0006", "framing on a full answer call", r"a few tokens per message, around (\d+) on a full answer call",
              kind="estimate", note=f"3 per message x (median fill {f['fill median SSU / KU / all'][2]:g} + system + question)"),
        Claim("0006", "no special-token text in the pool", r"No turn in the pool contains one today",
              f["special-token turns"] == 0),
        # 0007
        Claim("0007", "eligible questions", r"on the (\d+) eligible questions", (f["pool"],)),
        Claim("0007", "last 20 messages: min / max", r"hold ([\d,]+) to ([\d,]+) tokens", f["last20 min / max"]),
        Claim("0007", "last 20 messages: median SSU / KU",
              r"a median of about ([\d,]+) for `single-session-user` and ([\d,]+) for `knowledge-update`",
              f["last20 median SSU / KU"], kind="approx"),
        Claim("0007", "window binds before budget in every question",
              r"The window binds before the 8000-token budget in every question",
              f["window returns 20 messages"] == f["pool"],
              note=f"{f['window returns 20 messages']} of {f['pool']} return 20 messages"),
        Claim("0007", "budget fill: min / max / median range", r"takes (\d+) to (\d+) messages, a median of (\d+) to (\d+)",
              (*f["fill min / max"], min(f["fill median SSU / KU / all"][:2]), max(f["fill median SSU / KU / all"][:2]))),
        Claim("0007", "evidence in 20-message window: SSU / KU",
              r"inside the 20-message window in (\d+) of (\d+) `single-session-user` and (\d+) of (\d+) `knowledge-update`",
              (f["evidence in window SSU / KU"][0], f["pool SSU"], f["evidence in window SSU / KU"][1], f["pool KU"])),
        Claim("0007", "evidence in budget fill: SSU / KU", r"Inside the budget fill: (\d+) of (\d+) and (\d+) of (\d+)",
              (f["evidence in fill SSU / KU"][0], f["pool SSU"], f["evidence in fill SSU / KU"][1], f["pool KU"])),
        Claim("0007", "default turn window", r"`DEFAULT_HISTORY_TURNS`, (\d+) turns", (DEFAULT_HISTORY_TURNS,)),
        Claim("0007", "max_turns=None fails today", r"computes `max_turns \* 2`, which fails on `None`", _fails_on_none()),
        Claim("0007", "baseline sees evidence iff not long-term", r"those are the questions where the baseline can see it: (\d+) and (\d+)",
              f["evidence in fill SSU / KU"],
              note="sets coincide" if f["in fill exactly when not long-term"] else "sets DIFFER"),
        Claim("0007", "median messages in a budget fill", r"now returns about (\d+) messages rather than 20",
              (f["fill median SSU / KU / all"][2],), kind="approx"),
        Claim("0007", "largest message / newest never over",
              r"largest single message in the pool is ([\d,]+) tokens, but no question's newest message exceeds (\d+)",
              (f["largest message"], DEFAULT_BUDGET_TOKENS),
              note=f"newest over budget in {f['newest message over budget']}; fill over budget in {f['fill over budget']}"),
        # 0008
        Claim("0008", "LongMemEval grader commit", r"commit `(d0c699fa[0-9a-f]{32})`", kind="external",
              note="GitHub; evaluate_qa.py identical at d6dc8b5, checked in session"),
        Claim("0008", "integer answers in the pool", r"it is an integer in (\w+) questions", (f["integer answers"],)),
        Claim("0008", "time-worded questions / pool", r"All (\d+) time-worded questions among the (\d+)",
              (f["time-worded"], f["pool"]), note="depends on the TIME_WORDED pattern in this script"),
        Claim("0008", "…answer stated in the evidence", r"have their answer stated in the evidence itself", kind="estimate",
              note=f"{f['time-worded answered literally']} of {f['time-worded']} literally; the rest read by hand"),
        Claim("0008", "price per million input tokens", r"At \$([\d.]+) per million input tokens", kind="external",
              note="OpenRouter, checked in session 2026-09-26"),
        Claim("0008", "cost of one answer call", r"costs about \$([\d.]+)", kind="estimate",
              note="(8000 + ~250) input tokens at the price above"),
        Claim("0008", "cost of the pilot", r"the M1 pilot, 20 answer calls and 20 grading calls, under \$(\d+\.\d+)",
              kind="estimate"),
        # 0009
        Claim("0009", "SSU marking one turn", r"marks one turn in (\d+) of (\d+) questions",
              (f["SSU one evidence turn"], f["pool SSU"])),
        Claim("0009", "KU marking two turns in two sessions", r"marks two turns in two sessions in (\d+) of (\d+)",
              (f["KU two turns in two sessions"], f["pool KU"])),
        Claim("0009", "e66b632c example, quoted exactly", r"such as `e66b632c`: \"([^\"]+)\"",
              (f["e66b632c question"],), note="in pool" if f["e66b632c in pool"] else "NOT in pool"),
        Claim("0009", "breakdown split by the replay order of 0004",
              r"split into the earlier and the later by the replay order of 0004", True,
              note="statement of method; the order itself is checked under 0004"),
        Claim("0009", "KU questions outside the breakdown", r"The (\d+) `knowledge-update` questions that do not have exactly two evidence sessions",
              (f["KU not exactly two evidence sessions"],), note=f"evidence sessions per question: {f['KU evidence sessions per question']}"),
        Claim("0009", "E never empty", r"`E` is never empty", f["min evidence turns"] >= 1),
        Claim("0009", "orders identical in single-session-user", r"in `single-session-user` the two orders are the same",
              f["SSU orders identical"]),
        Claim("0009", "pilot size", r"among the (\d+) pilot questions", (2 * PILOT_PER_TYPE,)),
        Claim("0009", "precision bound: messages / low / high",
              r"about (\d+) messages recalled, a strategy that finds everything and fills the budget scores around (\d+\.\d+) to (\d+\.\d+)",
              (f["fill median SSU / KU / all"][2], round(1 / f["fill median SSU / KU / all"][2], 2),
               round(2 / f["fill median SSU / KU / all"][2], 2)), kind="approx", tolerance=0.2),
        Claim("0009", "one question in ten", r"one question moves a mean by (\d+\.\d+)", (1 / PILOT_PER_TYPE,)),
    ]


def _inclusive_at_limit() -> bool:
    limit = datetime(2023, 5, 30, 23, 59)
    memory = RecentTurnsMemory(max_turns=NO_WINDOW, token_counter=COUNTER)
    memory.write(MemoryRecord(id="s:0", role="user", content="x", kind="message", at=limit, session_id="s"))
    return memory.retrieve("q", at=limit, budget_tokens=DEFAULT_BUDGET_TOKENS).sources == ("s:0",)


def _fails_on_none() -> bool:
    try:
        RecentTurnsMemory(max_turns=None)  # type: ignore[arg-type]
    except TypeError:
        return True
    return False


def main() -> int:
    raw, data = load()
    f = compute_facts(raw, data)
    if "--facts" in sys.argv:
        for k, v in f.items():
            print(f"{k}: {v}")
        return 0
    claims = claims_for(f)
    texts = {p.name[:4]: re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))
             for p in sorted(ADR_DIR.glob("000[4-9]-*.md"))}
    for claim in claims:
        judge(claim, texts[claim.adr])

    header = ("ADR", "claim", "in text", "computed", "status", "note")
    table = [header] + [
        (c.adr, c.label, fmt(c.groups) if c.groups else ("(statement)" if c.status != "TEXT MISSING" else "—"),
         fmt(c.computed), c.status, c.note)
        for c in claims
    ]
    widths = [max(len(str(r[i])) for r in table) for i in range(len(header))]
    for n, r in enumerate(table):
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths)).rstrip())
        if n == 0:
            print("  ".join("-" * w for w in widths))
    tally = Counter(c.status for c in claims)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
