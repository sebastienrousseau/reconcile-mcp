<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- The `crewai` and `llamaindex` extras install from Python 3.11 only, and
  pull `pillow >= 13.0.0` (every earlier Pillow is advised, 5 critical) and,
  for `crewai`, `filelock >= 4.2.1` (GHSA-9vhv-jxww-xfm5, GHSA-567q-5qvw-pf92,
  GHSA-v4x8-3wr5-3wq8). Both fixes need Python 3.11; on 3.10 they had resolved
  Pillow 12.3.0 and filelock 4.1.0. The core package still supports 3.10, and
  on 3.10 those two extras now install nothing. `crewai` still brings
  chromadb, for which no fixed release exists.
- The release tooling (`requirements/build.txt`) floors `filelock >= 4.2.1`
  (GHSA-9vhv-jxww-xfm5, GHSA-567q-5qvw-pf92, GHSA-v4x8-3wr5-3wq8; it pinned
  4.0.10) and `certifi >= 2026.10.19` (PYSEC-2026-4320; it pinned
  2026.7.22), and keeps `virtualenv >= 21.14.13` (GHSA-cx6f-vjhg-g3cc).
  filelock 4.2.1 needs Python 3.11 and only 3.12 jobs install the tree, so
  it is compiled for 3.12, universally: that restores the pins (cachecontrol
  among them) a non-universal Dependabot recompile dropped, without which
  `pip install --require-hashes -r requirements/build.txt` failed.
- The release SBOM job points `cyclonedx-py environment` and `pip-licenses`
  at the Poetry venv (`poetry env info --executable`). Run through `poetry
  run`, they described their own interpreter, so the SBOM listed the SBOM
  tooling instead of the runtime set.
- `mcp >= 1.30.0, != 2.0.*, != 2.1.*` (GHSA-84m7-p3x7-pcfv), so neither
  affected range can resolve.
- `crewai` (optional) is declared for Python < 3.14, the range it supports.
  Without the marker Poetry could not resolve the project at all, which
  failed the release SBOM job since 0.0.6.

### Changed

- `requirements/build.in` floors `dulwich >= 1.2.19` (it pinned 1.2.17), in
  place of Dependabot #47 and #48.

## [0.0.7] - 2026-10-04

### Changed

- Standardize license section heading in README to License for Glama directory and registry matcher consistency.
- Update locked dependencies to resolve transitive vulnerabilities.

## [0.0.6] - 2026-10-03

### Added

- Agent framework adapters in `reconcile_mcp.framework_adapters` wrapping
  all 10 reconciliation gateway tools into native tool formats for
  LangChain (`as_langchain_tools`), CrewAI (`as_crewai_tools`), and
  LlamaIndex (`as_llamaindex_tools`) via optional lazy extras.
- Structured Tool Definition Quality Score (TDQS) descriptions across all 10
  MCP tools with explicit Purpose, When to use, When NOT to use,
  Behavioral transparency, and parameter constraints.
- `--transport streamable-http` and `--transport sse`, with `--host` and
  `--port`. Streamable HTTP serves both current protocol revisions
  (2026-07-28 stateless with `server/discover`, and 2025-11-25 with the
  `initialize` handshake) on one endpoint and streams responses as
  server-sent events; `sse` serves the older HTTP+SSE transport. stdio
  stays the default and is unchanged. `--version` prints the version.
  ADR 0001 records the decision.
- Governance and supply-chain files at suite parity: `AGENTS.md`, `Makefile`,
  `DEVELOPMENT.md`, `.editorconfig`, `.pre-commit-config.yaml`,
  `ARCHITECTURE.md`, `GOVERNANCE.md`, `ROADMAP.md`, `MAINTAINERS.md`,
  `RELEASING.md`, `SUPPORT.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`,
  `DCO.txt` and `docs/adr/`; OpenSSF Scorecard and DCO workflows;
  Dependabot; every action in every workflow pinned by commit SHA.
- Dual-licensing standard with full Apache-2.0 `LICENSE`, `LICENSE-APACHE`,
  `LICENSE-MIT`, and `LICENSES/` tree.

### Changed

- The server is built through a small compatibility shim so it runs on
  both supported majors of the `mcp` SDK: 2.x (`MCPServer`, the
  2026-07-28 stateless revision with `server/discover`) and 1.x
  (`FastMCP`). The dependency range is now `mcp>=1.2,<3`, so a fresh
  install gets 2.x and speaks the current protocol revision.

## [0.0.5] - 2026-08-29

Adds the scheduled release-consistency check this repository was
missing, and refreshes the shared conformance gate.

### Added

- `scripts/check_suite_consistency.py` and a scheduled **Release
  Consistency** workflow compare this tree against what is actually
  published on PyPI. A version bumped in the tree and never released
  breaks nothing — the tree is consistent, the tests pass, the changelog
  is written — and only the index disagrees. That has happened three
  times in this suite, each time stranding a security floor that reached
  nobody.
- The check distinguishes the two directions: a tree ahead of the index
  is the expected transient between merging a bump and pushing its tag,
  while a tree *behind* it means a release was cut from somewhere other
  than this branch.

### Changed

- Refreshed `tests/test_suite_conformance.py` to the current canonical
  copy. This repository was carrying a 24-invariant version; the
  twenty-fifth is the one that requires the check added above, so it had
  been conformant only against an older bar.

## [0.0.4] - 2026-08-29

Brings this repository onto the suite conformance gate. It had no
`CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/` or `benches/`.

### Added

- **`benches/bench_reconcile.py`**, and it found something that changes how
  this server should be used.

  **On clean data, matching is quadratic** — exponent ~2.0, which is what a
  pairwise matcher should be. 200 records takes about 0.5 s.

  **On realistic data it collapses.** With three kinds of discrepancy at
  once — some entries missing from the bank side, some references rewritten,
  some amounts short by a fee — the measured exponent is about **4.4**:

  | Records | One discrepancy type | Three at once |
  |---:|---:|---:|
  | 100 | 123 ms | **540 ms** |
  | 200 | 497 ms | **68,988 ms** |

  Doubling 100 to 200 multiplied the time by **128**, and the slope is still
  rising — the signature of a combinatorial search rather than a polynomial
  one. "Three at once" is not a stress case; it is what a month-end ledger
  looks like.

  **`reconcile_many_to_many` stays usable**: about 396 ms at 200 mixed
  records against 69 s for one-to-one, a **174x** gap in favour of the more
  general algorithm. That points at something specific in the one-to-one
  path rather than at the task being hard.

  It needs the `ilp` extra (scipy). Measured without it the solver degrades
  and returns almost instantly, which is easy to mistake for speed — the
  first draft of this benchmark did exactly that.

  Nothing is changed to address it. That is a substantial algorithmic fix
  with its own risks and deserves its own release rather than being
  smuggled into one that adds a benchmark. It is now measured, documented,
  and run by CI.

- **`docs/index.md`**, including the practical consequence: keep one-to-one
  batches under about 100 records and split larger ledgers by account, date
  or counterparty.

- **`SECURITY.md`**, which records this as an **availability** risk rather
  than a performance note. A caller can make the server unresponsive with a
  few hundred ordinary records — no malformed payload required.

- **`CONTRIBUTING.md`**, naming the exponent as the open problem and asking
  that any fix keep `explain_match` honest.

- **`tests/test_suite_conformance.py`** — invariants shared across the
  suite, vendored from one canonical copy and checksummed by its own test.

### Changed

- CI lints, formats and runs `benches/` alongside everything else.

[0.0.7]: https://github.com/sebastienrousseau/reconcile-mcp/releases/tag/v0.0.7
[0.0.6]: https://github.com/sebastienrousseau/reconcile-mcp/releases/tag/v0.0.6
[0.0.5]: https://github.com/sebastienrousseau/reconcile-mcp/releases/tag/v0.0.5
[0.0.4]: https://github.com/sebastienrousseau/reconcile-mcp/releases/tag/v0.0.4
