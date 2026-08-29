# reconcile-mcp

Match what you expected to be paid against what the bank says arrived.

```python
from reconcile_mcp.server import reconcile

result = reconcile(expected, observed)
result["summary"], result["matches"]
result["unmatched_expected"], result["unmatched_observed"]
```

## What it does

Reconciliation is the least glamorous and most necessary job in treasury.
You issued 400 invoices; the bank statement has 380 entries; the references
have been rewritten, three amounts are short by a fee, and two payments
cover five invoices each. Something has to work out which is which.

This server does that, and explains each decision so an agent can act on it
rather than just receive a verdict.

| Tool | What it answers |
|---|---|
| `reconcile` | One-to-one matching across two ledgers |
| `reconcile_many_to_many` | One payment settling several invoices |
| `explain_match` | Why *this* pair was matched, field by field |
| `match_names_probabilistic` | How alike two counterparty names are |
| `match_amounts_with_fx_drift` | Whether a difference is FX or an error |
| `normalize_pain001` / `normalize_camt053` | ISO 20022 documents into canonical records |
| `list_sandbox_scenarios` / `run_sandbox_scenario` | Worked scenarios to try it against |

## Scale — read this before running it on real data

`benches/bench_reconcile.py` measures how cost grows, which for a matcher is
the only question that matters.

**On clean data it is quadratic** — exponent ~2.0, which is what a pairwise
matcher should be. 200 records takes about 0.5 s.

**On realistic data it collapses.** With three kinds of discrepancy present
at once — some entries missing, some references rewritten, some amounts
short by a fee — the measured exponent is about **4.4**:

| Records | One discrepancy type | Three at once |
|---:|---:|---:|
| 25 | 8 ms | 7 ms |
| 50 | 31 ms | 31 ms |
| 100 | 123 ms | **540 ms** |
| 200 | 497 ms | **68,988 ms** |

Doubling 100 to 200 multiplied the time by **128**. The slope is still
rising, which is the signature of a combinatorial search rather than a
polynomial one.

**In practice: keep one-to-one reconciliation batches under about 100
records.** Beyond that, split the ledger — by account, by date, by
counterparty — so each batch stays small. A 1,000-record month-end run in
one call is not a slow operation, it is one that will not finish.

`reconcile_many_to_many` stays usable. It costs more per call — an ILP
solve rather than a scan — but grows gently: about **396 ms at 200 mixed
records**, where one-to-one takes **69 s**. A **174x** gap in favour of the
more general algorithm points at something specific in the one-to-one path
rather than at the difficulty of the task.

It requires the `ilp` extra (`pip install "reconcile-mcp[ilp]"`, which
brings scipy). Without it the solver degrades and returns almost
immediately — which is easy to mistake for it being fast.

*This is measured, not fixed. Treat the projection beyond 200 records as an
order of magnitude rather than a promise.*

## Canonical records

Both sides normalise to the same shape:

```python
{
    "id": "INV-000001",          # required
    "amount": 250.00,            # required
    "currency": "EUR",
    "reference": "Invoice 42",
    "counterparty": "Acme Supplier Ltd",
    "date": "2026-06-21",
}
```

`normalize_pain001` and `normalize_camt053` produce these from ISO 20022
documents, so the two sides of a reconciliation can come from different
message families without the caller reshaping anything.

## Explaining a match

`explain_match(expected, observed)` returns the per-field similarity that
produced a decision — reference, amount, date, counterparty — rather than a
bare score. That is the difference between an agent that can tell a human
*why* two records were paired and one that can only assert they were.

## Performance notes

- `match_names_probabilistic` costs about 0.5 µs per pair. Cheap alone; it
  is the inner cost a pairwise search multiplies.
- `reconcile_many_to_many` needs the `ilp` extra; without scipy it
  degrades rather than solving.
- Run `python benches/bench_reconcile.py --deep` to see the 200-record row.
  It takes over a minute, which is the point.

## Licence

Apache-2.0 OR MIT, at your option.
