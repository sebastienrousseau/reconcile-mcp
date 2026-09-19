<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.0.4]: https://github.com/sebastienrousseau/reconcile-mcp/releases/tag/v0.0.4
