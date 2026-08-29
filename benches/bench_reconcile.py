#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0 OR MIT
# Copyright (C) 2023-2026 Sebastien Rousseau. All rights reserved.
"""How reconciliation scales, which is the only question that matters here.

Matching expected records against observed ones is the classic quadratic
trap: for every expectation, consider every observation. That is fine on the
handful of records in a fixture and ruinous at month-end, when a mid-sized
corporate reconciles thousands of lines against thousands of bank entries.

What this measures, and what it found:

* **On clean data — one discrepancy type at a time — matching is
  quadratic**, an exponent near 2.0. Expected for a pairwise matcher.

* **With several discrepancy types at once it collapses.** The measured
  exponent is about **4.4** — worse than cubic, and the slope is still
  rising, which is the signature of a combinatorial search rather than a
  polynomial one.

  That matters because "several at once" is not a stress case, it is what
  a real ledger looks like: some entries missing, some references
  rewritten by the bank, some amounts short by a fee.

  Concretely: 100 records takes about 0.5 s, and 200 records takes about
  **69 s**. Doubling the input multiplied the time by 128.

* **``reconcile_many_to_many`` — the harder problem — stays usable.** It
  costs more per call (an ILP solve, not a scan) but grows gently: about
  396 ms at 200 mixed records, where one-to-one takes 69 s. That is a
  **174x** gap in favour of the more general algorithm, which points at a
  pathological search in the one-to-one path rather than at the task being
  hard.

  Note that many-to-many needs the ``ilp`` extra (scipy). Without it the
  solver degrades and returns almost immediately — measuring that instead
  of the real thing is an easy mistake, and this benchmark is only
  meaningful with the extra installed.

The number to read is the **growth exponent**, printed at the bottom.
Doubling the input and seeing time double is linear (~1.0); quadruple is
quadratic (~2.0); eight times is cubic (~3.0). Milliseconds on one machine
mean nothing; the exponent means everything.

Sizes are deliberately small. On mixed data 200 records already takes over
a minute, so the default stops at 100 and ``--deep`` opts into the row that
shows the curve breaking. A benchmark nobody will wait for is a benchmark
nobody runs.

Run::

    python benches/bench_reconcile.py
    python benches/bench_reconcile.py --json
    python benches/bench_reconcile.py --quick     # what CI runs

Nothing here asserts a threshold: wall-clock is not comparable between
machines, and a flaky performance gate teaches people to ignore red. CI
runs ``--quick`` so a benchmark that has stopped compiling against the
current API fails the build instead of rotting into a file that reads as
verified and is not.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reconcile_mcp import server  # noqa: E402


def build(size: int, *, mixed: bool) -> tuple[list[dict], list[dict]]:
    """Two ledgers to reconcile.

    With ``mixed=False`` every record differs only in counterparty spelling
    ("Ltd" against "Limited"), which is one discrepancy type. With
    ``mixed=True`` three are present at once: a tenth are missing from the
    bank side, a tenth have the reference rewritten, a tenth are short by a
    fee. That is what a real month-end looks like, and it is where the cost
    curve changes shape.
    """
    expected, observed = [], []
    for i in range(size):
        amount = round(100 + i + (i % 7) / 100, 2)
        expected.append(
            {
                "id": f"INV-{i:06d}",
                "amount": amount,
                "currency": "EUR",
                "reference": f"Invoice {i}",
                "counterparty": f"Acme Supplier {i % 50} Ltd",
                "date": "2026-06-21",
            }
        )
        bucket = i % 10
        if mixed and bucket == 9:
            continue
        record = dict(expected[-1])
        record["id"] = f"NTRY-{i:06d}"
        record["counterparty"] = f"Acme Supplier {i % 50} Limited"
        if mixed and bucket == 7:
            record["reference"] = f"INV{i} payment"
        if mixed and bucket == 8:
            record["amount"] = round(amount - 0.03, 2)
        observed.append(record)
    return expected, observed


def _best(call, repeats: int) -> float:
    """Best-of timing after one untimed warm-up.

    The minimum is the least noisy estimator available; the mean follows
    whatever else the machine is doing.
    """
    call()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    return min(samples)


def _safe(call):
    """Treat a refusal as a result: how fast it declines is a measurement."""

    def wrapped():
        try:
            return call()
        except Exception:
            return None

    return wrapped


def measure(size: int, repeats: int, *, mixed: bool) -> dict:
    expected, observed = build(size, mixed=mixed)
    one = _best(_safe(lambda: server.reconcile(expected, observed)), repeats)
    many = _best(
        _safe(lambda: server.reconcile_many_to_many(expected, observed)),
        repeats,
    )
    return {
        "size": size,
        "mixed": mixed,
        "reconcile_ms": one * 1e3,
        "many_to_many_ms": many * 1e3,
        "us_per_record": one * 1e6 / size,
    }


def _exponent(rows: list[dict], key: str) -> float:
    """Fit time = k * n**e over the measured points, returning e.

    A log-log slope: linear work gives about 1.0, quadratic about 2.0. Two
    points would be enough, but every pair is used so a single noisy row
    cannot decide the verdict on its own.
    """
    usable = [r for r in rows if r["size"] > 0 and r[key] > 0]
    if len(usable) < 2:
        return 0.0
    slopes = []
    for i in range(len(usable) - 1):
        a, b = usable[i], usable[i + 1]
        dn = math.log(b["size"] / a["size"])
        dt = math.log(b[key] / a[key])
        if dn:
            slopes.append(dt / dn)
    return sum(slopes) / len(slopes) if slopes else 0.0


def _verdict(exponent: float) -> str:
    """Name the growth class rather than judging the milliseconds."""
    if exponent < 1.3:
        return "linear — scales"
    if exponent < 1.7:
        return "super-linear — watch it"
    if exponent < 2.4:
        return "quadratic — expected for a pairwise matcher"
    if exponent < 3.4:
        return "CUBIC — small ledgers only"
    return "WORSE THAN CUBIC — combinatorial, bounded by patience"


def run(quick: bool, deep: bool = False) -> dict:
    # 200 mixed records already takes over a minute, so the default stops
    # at 100 and --deep opts into the row that shows the curve breaking.
    if quick:
        sizes, repeats = [25, 50], 1
    elif deep:
        sizes, repeats = [25, 50, 100, 200], 3
    else:
        sizes, repeats = [25, 50, 100], 3
    return {
        "clean": [measure(n, repeats, mixed=False) for n in sizes],
        "mixed": [measure(n, repeats, mixed=True) for n in sizes],
        "name_match_us": _best(
            lambda: server.match_names_probabilistic(
                "Acme Supplier 12 Ltd", "Acme Supplier 12 Limited"
            ),
            200 if quick else 2_000,
        )
        * 1e6,
    }


def render(results: dict) -> None:
    for label, key in (
        ("one discrepancy type", "clean"),
        ("three at once", "mixed"),
    ):
        rows = results[key]
        print(
            f"{label} — {'clean data' if key == 'clean' else 'a real month-end'}"
        )
        print(
            f"{'records':>9}{'reconcile ms':>15}{'many-to-many ms':>18}"
            f"{'us/record':>12}"
        )
        for row in rows:
            print(
                f"{row['size']:>9}{row['reconcile_ms']:>15.1f}"
                f"{row['many_to_many_ms']:>18.2f}{row['us_per_record']:>12.0f}"
            )
        print()

    clean = _exponent(results["clean"], "reconcile_ms")
    mixed = _exponent(results["mixed"], "reconcile_ms")
    m2m = _exponent(results["mixed"], "many_to_many_ms")
    print(
        f"  growth exponent — one discrepancy type  {clean:.2f}  ({_verdict(clean)})"
    )
    print(
        f"                    three at once         {mixed:.2f}  ({_verdict(mixed)})"
    )
    print(
        f"                    many-to-many, mixed   {m2m:.2f}  ({_verdict(m2m)})"
    )
    print(
        "\n  Doubling the input and seeing time double is linear (~1.0);\n"
        "  quadruple is quadratic (~2.0); eight times is cubic (~3.0).\n"
        "  A pairwise matcher is expected to be quadratic. What is worth\n"
        "  attention is the gap between the two rows above: several kinds\n"
        "  of discrepancy at once cost more than the sum of each alone, and\n"
        "  that combination is the normal case rather than the stress case."
    )
    if mixed > clean + 0.5:
        biggest = results["mixed"][-1]
        projected = (
            biggest["reconcile_ms"] * (1_000 / biggest["size"]) ** mixed / 1000
        )
        print(
            f"\n  At {biggest['size']} mixed records reconcile takes "
            f"{biggest['reconcile_ms']:,.0f} ms. At exponent {mixed:.2f}, "
            f"1,000 records projects to roughly {projected:,.0f} s.\n"
            f"  Treat that as an order of magnitude, not a promise — but it "
            f"is the number that decides whether month-end fits in a job."
        )
    print(
        f"\n  match_names_probabilistic: {results['name_match_us']:,.1f} us "
        f"per pair — the inner cost a pairwise search multiplies."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--quick", action="store_true", help="small sizes, as CI runs"
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="add the 200-record row; takes over a minute on mixed data",
    )
    args = parser.parse_args()

    results = run(quick=args.quick, deep=args.deep)
    if args.json:
        json.dump(results, sys.stdout, indent=1)
        print()
    else:
        render(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
