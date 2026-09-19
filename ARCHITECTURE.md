<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# reconcile-mcp Architecture

A map of the codebase for new contributors and maintainers. The goal is
that anyone can navigate, extend, and reason about reconcile-mcp without
prior context.

## The pipeline

```
MCP client (Claude Desktop, IDE, agent)
        |  stdio, streamable HTTP or SSE (JSON-RPC)
        v
reconcile_mcp/server.py      (MCP server: tools, prompt, resources)
        |  thin typed wrappers
        v
reconcile_mcp/engine.py      (pure matching core: scoring, greedy
        |                     assignment, one-to-many, many-to-one,
        |                     subset-sum ILP via optional scipy)
reconcile_mcp/adapters.py    (pain.001 / camt.053 -> canonical records)
reconcile_mcp/sandbox.py     (deterministic test-mode scenarios)
        v
explainable match report (matches, scores, reasons, residuals)
```

Tools are deliberately thin: every one is a small adapter that
delegates to the matching core and returns a JSON-serialisable result.
Nothing opens a caller-supplied path or reaches an external system; the
whole server computes from its arguments and the bundled fixtures.

## Module map

| Area | Module | Responsibility |
| :--- | :--- | :--- |
| **Server** | `reconcile_mcp/server.py` | The MCP server, all tool / prompt / resource registrations |
| **Entry point** | `reconcile_mcp.server:main` (console script: `reconcile-mcp`) | Launches the server over stdio, or over streamable HTTP / SSE with `--transport` (`_cli.py` + `_transports.py`, ADR 0001) |
| **SDK shim** | `reconcile_mcp/_mcp_compat.py` | Builds the server on either supported major of the `mcp` SDK (2.x `MCPServer`, 1.x `FastMCP`) |
| **Matching core** | `reconcile_mcp/engine.py` | Scores candidate pairs on reference, amount, date and counterparty; assigns greedily and deterministically; finds one-to-many and many-to-one groups; solves many-to-many as a bounded subset-sum ILP when scipy is present |
| **Adapters** | `reconcile_mcp/adapters.py` | Reshape parsed `pain.001` (expected side) and `camt.053` (observed side) into canonical records |
| **Sandbox** | `reconcile_mcp/sandbox.py` | Built-in scenarios so the whole flow runs with no real cash data |
| **Version** | `reconcile_mcp/__init__.py` | Single source of truth (`__version__`) |
| **Tests** | `tests/test_server.py`, `tests/test_engine.py`, `tests/test_matching_tier2.py`, `tests/test_adapters.py`, `tests/test_sandbox.py`, `tests/test_transports.py`, `tests/test_mcp_sdk_compat.py`, `tests/test_suite_conformance.py` | The tool surface, the core, the tier-2 matchers, the adapters, the sandbox, the command line, the SDK shim, and the shared suite conformance gate |
| **Examples** | `examples/mcp_tools.py` | Runnable in-process walkthrough of the tools |
| **Benchmarks** | `benches/bench_reconcile.py` | How cost grows with record count; `docs/index.md` explains the result |
| **Release helpers** | `scripts/verify_versions.py`, `scripts/check_suite_consistency.py` | Assert every restatement of the version agrees; compare the tree against PyPI |

## Tools, prompt, resources

The current MCP surface:

- **Tools** - ten. Matching: `reconcile` (one-to-one with one-to-many
  and many-to-one residual passes), `reconcile_many_to_many` (subset-sum
  ILP; needs the `ilp` extra), `explain_match` (one pair, per-signal
  breakdown), `match_names_probabilistic` (Jaro-Winkler),
  `match_amounts_with_fx_drift` (two currencies through a supplied
  rate). Adapters: `normalize_pain001`, `normalize_camt053`. Sandbox:
  `list_sandbox_scenarios`, `load_sandbox_scenario`,
  `run_sandbox_scenario`.
- **Prompt** - `reconcile_workflow(scenario)` (the normalize, reconcile,
  explain workflow, optionally walked through on one scenario).
- **Resources** - `reconcile://sandbox-scenarios` (the catalogue) and
  `reconcile://sandbox/{scenario_id}` (one scenario's inputs).

## Key design decisions

- **Explain, do not just decide.** Every match carries a score and the
  list of signals that drove it; `explain_match` exposes the same
  breakdown for any pair. A faster matcher that cannot say why is a
  worse tool.
- **Deterministic.** Assignment is greedy, highest score first, with a
  total tiebreak order, so the same inputs always give the same result.
- **Errors as data.** Tools never raise. A `ValueError` is turned into
  an `{"error": ...}` payload so the agent can reason about failure
  without parsing tracebacks.
- **Pure readers.** Every tool is annotated `readOnlyHint` and
  `idempotentHint`, never `destructiveHint`, and closed-world: nothing
  reads a path or reaches the network.
- **Heavy solver optional.** scipy powers the subset-sum ILP and is an
  extra (`reconcile-mcp[ilp]`); without it `reconcile_many_to_many`
  returns an error payload rather than pulling in a large dependency
  for everyone.
- **Loopback by default.** stdio needs no socket. The HTTP transports
  bind `127.0.0.1` unless told otherwise and add no authentication of
  their own; a routable deployment sits behind a gateway (ADR 0001).
- **Known limit, recorded.** The one-to-one matcher's growth on messy
  data (exponent about 4.4) is measured by the benchmark and stated in
  `SECURITY.md` as an availability risk; see `ROADMAP.md`.
- **Coverage enforced at 100%** line+branch; only defensive guards are
  `# pragma: no cover`.

## Extension points

- **Add a tool:** add a function under `@server.tool(...)` in
  `reconcile_mcp/server.py` that delegates to `engine`, `adapters` or
  `sandbox`; pair it with tests in `tests/test_server.py` and the
  module's own test file.
- **Add an adapter:** a `normalize_*` function in
  `reconcile_mcp/adapters.py` that yields canonical records (`id` and
  `amount` required).
- **Add a sandbox scenario:** register it in `reconcile_mcp/sandbox.py`;
  it appears in the catalogue resource and `list_sandbox_scenarios`.
- **Change the matcher:** report the growth exponent from
  `benches/bench_reconcile.py --deep` before and after.

## Where to look first

- Runnable example: [`examples/`](examples/)
- What the tools answer and how cost grows: [`docs/index.md`](docs/index.md)
- Decisions: [`docs/adr/`](docs/adr/index.md)
- Roadmap: [`ROADMAP.md`](ROADMAP.md)
- Release process: [`RELEASING.md`](RELEASING.md)
