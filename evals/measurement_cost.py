"""What the measurement cost, in dollars and in SEK (ADR 0010).

ADR 0010 converts the cap of 1000 SEK at the ECB rate and leaves it to the
report to state what the credits actually cost in SEK. This script does that,
and keeps two kinds of figures apart:

* Computed here: the harness's own count of every committed row that called a
  model (evals/results/, the spike's replies included), and every sum, rate
  and share printed below.
* External: the author's readings of the OpenRouter account before and after
  each milestone's runs, and the two receipts for the credits with what the
  bank charged for them. They are constants here, with their dates, and
  cannot be recomputed.

What the account spent between a reading before a milestone's runs and the
reading after them is taken as the measurement's. What it spent outside those
readings is not: the account is from May 2026, and the harness made its first
call on 27 September, the day of its first commit (b336397) and of the M1
pilot.

    .venv/bin/python evals/measurement_cost.py            # the table
    .venv/bin/python evals/measurement_cost.py --check    # docs/vg-project.md against this script
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.estimate_cost import BILLED_DAY, CAP_SEK, SEK_PER_USD  # noqa: E402
from evals.longmemeval import cost_of  # noqa: E402
from evals.verify_adr_numbers import ROOT, Claim, fmt, judge  # noqa: E402

RESULTS = ROOT / "evals" / "results"
DOC = ROOT / "docs" / "vg-project.md"
# The milestone a committed run belongs to, by the date in its file name. The spike's replies are M4's.
MILESTONES = {"20260927": "M1", "20261002": "M2", "20261003": "M3", "20261005": "M4"}
M4_SMOKE, M4_PILOT = "fact-graph-20261005-153720-smoke.jsonl", "fact-graph-20261005-161632.jsonl"
# The credits, as the author read the receipts and the bank statement on 2026-10-04: dollars of credits,
# dollars on OpenRouter's receipt, SEK charged by the bank, the receipt's date, the bank's date.
PURCHASES = (
    (10.00, 12.96, 124.23, date(2026, 5, 20), date(2026, 5, 21)),
    (50.00, 65.94, 676.02, date(2026, 10, 2), date(2026, 10, 3)),
)
# Dollars the account had used since it was opened, read by the author before and after a milestone's
# runs: M2 on 2 and 3 October, M3 on 3 and 4 October. M1 has no such pair. Its figure is what
# OpenRouter's activity page billed for 27 September, the pilot and one check call (BILLED_DAY, ADR 0010).
USED = {"M2": (9.08, 14.25), "M3": (14.25, 27.78)}
# 5 October, read as credits left: before the spike, after it, after the smoke test, after the pilot.
LEFT_M4 = (32.14, 31.57, 31.46, 30.31)
# What docs/vg-project.md first took off the account's usage to get the measurement: what the account
# spent in September, the M1 pilot included. Kept to show where the figures it replaced came from.
SEPTEMBER = 0.88


def harness() -> dict:
    """The harness's count of every committed row that called a model, each call at its model's price."""
    runs = {}
    for path in sorted(RESULTS.glob("*.jsonl")):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if "calls" in rows[0] and not rows[0]["dry_run"]:  # neither a listing of facts nor a dry run
            runs[path.name] = sum(cost_of(r["calls"]) for r in rows)
    spike = sum(cost_of(json.loads(line)["calls"]) for path in sorted((RESULTS / "spike").glob("*.jsonl"))
                for line in path.read_text(encoding="utf-8").splitlines())
    by = dict.fromkeys(MILESTONES.values(), 0.0)
    for name, cost in runs.items():
        by[MILESTONES[re.search(r"-(\d{8})-", name).group(1)]] += cost
    by["M4"] += spike
    return dict(by=by, total=sum(by.values()), m4_parts=(spike, runs[M4_SMOKE], runs[M4_PILOT]))


def compute() -> dict:
    by = {"M1": BILLED_DAY, **{m: after - before for m, (before, after) in USED.items()},
          "M4": LEFT_M4[0] - LEFT_M4[-1]}
    total = sum(by.values())
    credits, receipts, charged = (sum(p[i] for p in PURCHASES) for i in range(3))
    rate = charged / credits
    used = credits - LEFT_M4[-1]
    # Outside the measurement: before M2's first reading and not M1's day, and between M3 and M4.
    outside = (USED["M2"][0] - BILLED_DAY, credits - LEFT_M4[0] - USED["M3"][1])
    wrong = USED["M3"][1] - SEPTEMBER
    return dict(harness=harness(), by=by, total=total, at_m3=total - by["M4"],
                m4_parts=tuple(before - after for before, after in zip(LEFT_M4, LEFT_M4[1:])),
                credits=credits, receipts=receipts, charged=charged, rate=rate,
                sek=total * rate, share=total * rate / CAP_SEK, cap_usd=CAP_SEK / rate,
                used=used, outside=outside, superseded=(wrong, wrong + by["M4"]))


def day(d: date) -> str:
    return f"{d.day} {d:%B}"


def print_table(f: dict) -> None:
    h = f["harness"]
    print("credits bought                         credits   receipt   charged   SEK per credit dollar")
    for usd, receipt, sek, bought, booked in PURCHASES:
        print(f"  {bought} (charged {booked})    ${usd:6.2f}   ${receipt:6.2f}   {sek:7.2f}   {sek / usd:.4f}")
    print(f"  {'together':31s}    ${f['credits']:6.2f}   ${f['receipts']:6.2f}   {f['charged']:7.2f}   {f['rate']:.4f}")
    print("\nthe measurement, in dollars            account   harness")
    for m in f["by"]:
        print(f"  {m:36s} {f['by'][m]:8.4f}  {h['by'][m]:8.4f}")
    print(f"  {'total':36s} {f['total']:8.4f}  {h['total']:8.4f}")
    print(f"  {'at the close of M3':36s} {f['at_m3']:8.4f}  {h['total'] - h['by']['M4']:8.4f}")
    print(f"  M4's spike / smoke test / pilot: {fmt(f'{v:.2f}' for v in f['m4_parts'])} by the account, "
          f"{fmt(f'{v:.2f}' for v in h['m4_parts'])} by the harness")
    print(f"\nin SEK at the price paid, {f['rate']:.4f} a credit dollar: {f['sek']:.2f}, {f['share']:.0%} of the cap of {CAP_SEK}")
    print(f"in SEK at 0010's rate, {SEK_PER_USD}: {f['total'] * SEK_PER_USD:.2f}")
    print(f"the cap in credit dollars at the price paid: ${f['cap_usd']:.2f} (0010: ${CAP_SEK / SEK_PER_USD:.2f})")
    print(f"the account has used ${f['used']:.2f} of ${f['credits']:.2f}; outside the measurement: ${sum(f['outside']):.2f}, "
          f"${f['outside'][0]:.2f} before the harness's first call and ${f['outside'][1]:.2f} between M3 and M4")
    print(f"superseded: ${f['superseded'][0]:.2f} at the close of M3 and ${f['superseded'][1]:.2f} after M4, "
          f"the account's usage less September's ${SEPTEMBER:.2f}")


def claims(f: dict) -> list[Claim]:
    h, by = f["harness"], f["by"]
    money = lambda v: f"{v:.2f}"  # noqa: E731
    first, second = PURCHASES
    return [
        Claim("cost", "M3's close", r"measurement had cost \$(\d+\.\d+) by then; the \$(\d+\.\d+) first written here",
              (money(f["at_m3"]), money(f["superseded"][0]))),
        Claim("cost", "M4's parts: account / harness",
              r"the spike cost \$(\d+\.\d+), the smoke test \$(\d+\.\d+) and the pilot run \$(\d+\.\d+) "
              r"\(\$(\d+\.\d+), \$(\d+\.\d+) and \$(\d+\.\d+) by the harness's count\)",
              (*map(money, f["m4_parts"]), *map(money, h["m4_parts"]))),
        Claim("cost", "the measurement, by milestone",
              r"has cost \*\*\$(\d+\.\d+)\*\*.*?\$(\d+\.\d+) for M1, \$(\d+\.\d+) for M2, \$(\d+\.\d+) for M3 and \$(\d+\.\d+) for M4",
              (money(f["total"]), *(money(by[m]) for m in by))),
        Claim("cost", "the harness's count", r"The harness counts \$(\d+\.\d+) for the calls in the committed rows", (money(h["total"]),)),
        Claim("cost", "the dates: bought / charged", r"bought on (\d+ \w+) and (\d+ \w+) 2026, and the bank charged them on (\d+ \w+) and (\d+ \w+)",
              (day(first[3]), day(second[3]), day(first[4]), day(second[4]))),
        Claim("cost", "the two purchases", r"\$(\d+) of credits for (\d+\.\d+) SEK and \$(\d+) for (\d+\.\d+) SEK",
              (first[0], money(first[2]), second[0], money(second[2]))),
        Claim("cost", "the receipts", r"The receipts come to \$(\d+\.\d+) for the \$(\d+) of credits", (money(f["receipts"]), f["credits"])),
        Claim("cost", "the price of a credit dollar", r"(\d+\.\d+) SEK for \$(\d+), or (\d+\.\d+) SEK a credit dollar, where 0010 converted the cap at (\d+\.\d+)",
              (money(f["charged"]), f["credits"], money(f["rate"]), money(SEK_PER_USD))),
        Claim("cost", "the measurement in SEK", r"has cost about \*\*(\d+) SEK\*\*, (\d+)% of the cap of (\d+) SEK",
              (round(f["sek"]), round(100 * f["share"]), CAP_SEK)),
        Claim("cost", "the cap in credit dollars", r"the cap is \$(\d+\.\d+) of credits, not the \$(\d+\.\d+)",
              (money(f["cap_usd"]), money(CAP_SEK / SEK_PER_USD))),
        Claim("cost", "the account's usage", r"The account has used \$(\d+\.\d+) in all, and the other \$(\d+\.\d+)",
              (money(f["used"]), money(sum(f["outside"])))),
        Claim("cost", "outside the measurement", r"\$(\d+\.\d+) of it was used before the harness made its first call.*?The last \$(\d+\.\d+) was used between",
              tuple(map(money, f["outside"]))),
        Claim("cost", "the harness's first day", r"the harness and the M1 pilot are of (\d+ \w+)", (day(datetime.strptime(next(iter(MILESTONES)), "%Y%m%d")),)),
        Claim("cost", "the figures replaced", r"The close of M3 said \$(\d+\.\d+) and the close of M4 \$(\d+\.\d+)", tuple(map(money, f["superseded"]))),
        Claim("cost", "what the replaced figures took off", r"less the \$(\d+\.\d+) it used in September.*?had used \$(\d+\.\d+) when M2 began.*?only M1's \$(\d+\.\d+)",
              (money(SEPTEMBER), money(USED["M2"][0]), money(BILLED_DAY))),
    ]


def main() -> int:
    f = compute()
    if "--check" not in sys.argv:
        print_table(f)
        return 0
    text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
    cs = claims(f)
    for c in cs:
        judge(c, text)
        print(f"{c.status:12s} {c.label:36s} text {fmt(c.groups) if c.groups else '—':52s} computed {fmt(c.computed)}")
    tally = Counter(c.status for c in cs)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("DIFF") or tally.get("TEXT MISSING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
