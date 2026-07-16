# reconcile-mcp: An MCP Server for ISO 20022 Cash Reconciliation

**A [Model Context Protocol][mcp] server that matches *expected* payments
(from `pain.001` credit transfers) against *observed* booked entries (from a
`camt.053` statement) and returns an explainable reconciliation** — exact
matches, short/over payments, split settlements (one-to-many), batch credits
(many-to-one), and the residual unmatched items on each side, every match
carrying a score and the reasons it was made.

> **Latest release: v0.0.1** — 7 MCP tools over stdio, pure-Python matching
> engine, deterministic sandbox test-mode, for Python 3.10+. Part of the
> [ISO 20022 MCP suite](#the-iso-20022-mcp-suite): you own both sides of the
> match.

## Why this exists

Reconciliation is the treasury team's daily pain: did the money we *expected*
actually *arrive*, and which invoice does each credit belong to? It is rarely
one-to-one — customers underpay, settle an invoice in instalments, or a payout
aggregator sends one lump covering a dozen receivables. `reconcile-mcp` does
this matching as an agent tool, and — critically for finance — **shows its
work**: every pairing comes with a numeric score and a plain list of the
signals (reference, amount, date, counterparty) that drove it.

## The ISO 20022 MCP Suite

`reconcile-mcp` is the **reconciliation workflow** of four coordinated,
vendor-neutral MCP servers that together cover the ISO 20022 bank-statement
workflow — statement depth, whole-catalogue routing, reconciliation, and
multi-format ingestion. Dependency ranges are kept aligned across the suite,
so the servers co-install cleanly in a single Python environment: start with
one, add the rest as your workflow grows.

| Server | Scope | Surface | Install | Use it when |
| --- | --- | --- | --- | --- |
| [`camt053-mcp`][camt053-mcp] | ISO 20022 `camt.053`/`camt.052` bank statements: parse, validate, filter, reverse; MT940/MT942 migration; CBPR+ readiness; journal export | 22 MCP tools · 4 prompts · 3 resources | `pip install camt053-mcp` | You work with bank-to-customer statements end to end — the suite's flagship |
| [`iso20022-mcp`][iso20022-mcp] | Unified gateway: `search` / `describe` / `validate` / `generate` / `parse` meta-tools routed across the `pain` · `pacs` · `camt` · `acmt` families | 7 meta-tools | `pip install "iso20022-mcp[all]"` | You want one entry point to every message family |
| [`reconcile-mcp`](#install) | Matches expected `pain.001` payments against observed `camt.053` entries — exact, partial, one-to-many, many-to-one, every match scored and explained | 7 MCP tools | `pip install reconcile-mcp` | You need explainable statement/payment reconciliation — **this package** |
| [`bankstatementparser-mcp`][bsp-mcp] | Multi-format statement ingestion: ISO 20022 CAMT.053 and pain.001, SWIFT MT940, OFX/QFX, CSV | 5 MCP tools · 1 prompt · 1 resource | `pip install bankstatementparser-mcp` | Your statements arrive in mixed or legacy formats |

In one line each: **`camt053-mcp`** is the bank-statement flagship (deepest
camt.05x surface, stdio + authenticated streamable HTTP);
**`iso20022-mcp`** is the generic message toolkit (a handful of verbs over
the whole catalogue); **`reconcile-mcp`** is the reconciliation workflow
(did the money we expected actually arrive?); and
**`bankstatementparser-mcp`** is the ingestion layer (many formats in, one
transaction shape out).

The suite also includes per-family servers — [`pain001-mcp`][pain001-mcp]
(credit transfer initiation), [`pacs008-mcp`][pacs008-mcp] (FI-to-FI credit
transfers), and [`acmt001-mcp`][acmt001-mcp] (account management) — whose
parsed output feeds straight into this server's `normalize_*` adapters.

## Install

```sh
pip install reconcile-mcp
# or run without installing:
uvx reconcile-mcp
```

MCP client config (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "reconcile": {
      "command": "reconcile-mcp"
    }
  }
}
```

## Quick start (zero real data)

The server ships a **sandbox test-mode**: deterministic scenarios so you can
run the whole flow with no setup and no real cash data. One call gets you a
full, explainable result:

```
run_sandbox_scenario(name="month_end")
```

returns a realistic mixed close — one clean match, one short payment, one split
settlement, and an unexpected credit correctly left unmatched:

```jsonc
{
  "summary": {
    "expected_count": 3, "observed_count": 5,
    "matched_expected": 3, "unmatched_observed": 1,
    "matches_by_type": {"exact": 1, "amount_mismatch": 1, "one_to_many": 1},
    "fully_reconciled": false
  },
  "matches": [
    {"type": "amount_mismatch", "expected": ["INV-6002"], "observed": ["ENT-52"],
     "amount_delta": "-99.99", "confidence": "high",
     "reasons": ["reference exact", "amount close (delta -99.99)", "date +/-0d", "counterparty exact"]},
    {"type": "exact", "expected": ["INV-6001"], "observed": ["ENT-51"], "amount_delta": "0.00"},
    {"type": "one_to_many", "expected": ["INV-6003"], "observed": ["ENT-53", "ENT-54"],
     "reasons": ["amount sum of 2 entries"]}
  ],
  "unmatched_observed": ["ENT-55"]
}
```

List every scenario with `list_sandbox_scenarios`; load one to inspect or edit
its inputs with `load_sandbox_scenario`.

## Bring your own data

Records are small canonical objects — `id` and `amount` required, everything
else optional and used to sharpen matching:

```jsonc
{
  "id": "INV-1001",            // your reference / end-to-end id
  "amount": 1200.00,
  "currency": "EUR",           // ISO 4217
  "date": "2026-03-02",        // ISO-8601
  "counterparty": "Acme Ltd",
  "reference": "INV-1001"      // remittance / structured reference
}
```

Already using the rest of the suite? Feed parsed output straight in — the
adapters map it for you:

- `normalize_pain001(document)` → the *expected* side, from
  [`pain001-mcp`][pain001-mcp].
- `normalize_camt053(document)` → the *observed* side, from
  [`camt053-mcp`][camt053-mcp].

Then call `reconcile(expected, observed)`.

## Tools

| Tool | What it does |
| --- | --- |
| `reconcile` | Match expected payments against observed entries; full explainable report. |
| `explain_match` | Score a single expected/observed pair with a per-signal breakdown (tuning aid). |
| `normalize_pain001` | Adapt parsed `pain.001` output into canonical *expected* records. |
| `normalize_camt053` | Adapt parsed `camt.053` output into canonical *observed* records. |
| `list_sandbox_scenarios` | List the built-in test-mode scenarios and magic references. |
| `load_sandbox_scenario` | Return one scenario's expected/observed inputs to inspect or edit. |
| `run_sandbox_scenario` | Load a scenario and reconcile it in one call — the fastest first run. |

## How matching works

Each candidate pair is scored on four weighted signals, then classified:

- **Reference** (0.45) — exact / partial equality of references and end-to-end
  ids, normalised to bare alphanumerics.
- **Amount** (0.35) — exact within tolerance, or a linearly-decaying closeness
  with the delta reported.
- **Date** (0.10) — proximity within a configurable window; neutral if unknown.
- **Counterparty** (0.10) — token-set overlap of names; neutral if unknown.

Assignment is greedy, highest-score-first and fully deterministic (a total
tiebreak order), so the same inputs always produce the same result. Residuals
are then tested for **one-to-many** (a bounded subset-sum: one expected settled
by several entries) and **many-to-one** (one entry covering several expected).

Tune any of it via the `options` argument: `abs_tol` / `rel_tol`,
`date_window_days`, `high_threshold`, `review_threshold`, `currency_strict`,
`enable_one_to_many`, `max_combination`.

## Development

```sh
git clone https://github.com/sebastienrousseau/reconcile-mcp
cd reconcile-mcp
python -m venv .venv && . .venv/bin/activate
pip install -e . && pip install pytest pytest-cov ruff black mypy
pytest                      # 100% branch coverage gate
ruff check reconcile_mcp tests && black --check reconcile_mcp tests && mypy reconcile_mcp
```

## Licence

Licensed under the [Apache License, Version 2.0](LICENSE).

---

`mcp-name: io.github.sebastienrousseau/reconcile-mcp`

[mcp]: https://modelcontextprotocol.io
[iso20022-mcp]: https://github.com/sebastienrousseau/iso20022-mcp
[pain001-mcp]: https://github.com/sebastienrousseau/pain001-mcp
[pacs008-mcp]: https://github.com/sebastienrousseau/pacs008-mcp
[camt053-mcp]: https://github.com/sebastienrousseau/camt053-mcp
[acmt001-mcp]: https://github.com/sebastienrousseau/acmt001-mcp
[bsp-mcp]: https://github.com/sebastienrousseau/bankstatementparser-mcp
