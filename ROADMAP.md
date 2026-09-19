# reconcile-mcp Roadmap

This roadmap tracks what is planned for the reconciliation server of the
ISO 20022 MCP suite. It summarises the CHANGELOG and the open issues; it
does not promise work that is not tracked there. Releases ship when the
gates pass, not on a calendar.

## v0.0.5 (current)

- Ten tools: `reconcile`, `explain_match`, `reconcile_many_to_many`,
  `match_names_probabilistic`, `match_amounts_with_fx_drift`,
  `normalize_pain001`, `normalize_camt053`, `list_sandbox_scenarios`,
  `load_sandbox_scenario` and `run_sandbox_scenario`; one prompt
  (`reconcile_workflow`) and two resources
  (`reconcile://sandbox-scenarios`, `reconcile://sandbox/{scenario_id}`).
- 100% line+branch coverage gate, the shared suite conformance test, a
  growth benchmark that CI keeps runnable, and a scheduled check that
  the tree agrees with what is published on PyPI.

## Next release (on `main`, unreleased)

- stdio, streamable HTTP (2026-07-28 and 2025-11-25) and SSE from one
  command line (ADR 0001).
- Runs on both supported majors of the `mcp` SDK through a
  compatibility shim; a fresh install gets 2.x.
- Governance and supply-chain files at suite parity: Scorecard, DCO,
  Dependabot, actions pinned by commit SHA.

## The open problem

The one-to-one matcher (`reconcile`) is quadratic on clean data and
collapses on realistic data: with several kinds of discrepancy present
at once the measured growth exponent is about 4.4, and 200 records take
about a minute. `reconcile_many_to_many`, the harder problem, stays
flat. The 0.0.4 changelog records this as measured, not fixed, because
the fix deserves its own release. It is the most valuable thing to work
on here; see [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules
(move the exponent, keep `explain_match` honest, add a test at a size
that would catch a regression). No release is scheduled for it yet.

## Beyond

No further work is scheduled. There are no open issues at the time of
writing. New adapters follow the suite: when a sibling server's parsed
output is worth feeding in directly, a `normalize_*` tool is added here.

## Out of scope (handled elsewhere)

- **Parsing bank statements** - see
  [`camt053-mcp`](https://github.com/sebastienrousseau/camt053-mcp) and
  [`bankstatementparser-mcp`](https://github.com/sebastienrousseau/bankstatementparser-mcp);
  `normalize_camt053` only reshapes their output.
- **Generating or validating payment files** - see
  [`pain001-mcp`](https://github.com/sebastienrousseau/pain001-mcp);
  `normalize_pain001` only reshapes its output.
