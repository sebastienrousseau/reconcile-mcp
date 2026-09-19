<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# reconcile-mcp Governance

This document describes how reconcile-mcp is run, how decisions are made,
and how to take on responsibility for it. It exists to make the project
legible and sustainable - and, candidly, to reduce its dependence on any
single person.

## Mission and scope

reconcile-mcp is the reconciliation workflow of the ISO 20022 MCP suite.
It matches expected payments (`pain.001` credit transfers) against
observed bank-statement entries (`camt.053`) and returns an explainable
result: exact, partial, one-to-many, many-to-one and subset-sum matches,
each with a score and the reasons it was made, plus the residual
unmatched items on each side. It exposes that as MCP tools, one prompt
and two resources so AI agents can drive a close. Changes are weighed
against that scope: correctness, explainability, security and clarity
over feature breadth. Parsing statements and generating payment files
belong to the sibling servers, not here.

## Roles

| Role | Who | Can |
| :--- | :--- | :--- |
| **Maintainer** | Listed in [`MAINTAINERS.md`](MAINTAINERS.md) | Merge PRs, cut releases, triage, set direction |
| **Contributor** | Anyone with a merged PR | Propose changes, review, discuss |
| **User** | Everyone | File issues, ask questions, request features |

## Decision making

- **Day-to-day changes** (fixes, docs, tests, additive features within
  scope) proceed by **lazy consensus**: open a PR; if no maintainer
  objects and CI is green, a maintainer merges it.
- **Significant changes** (new public APIs, breaking changes, new
  dependencies, new tools/resources/prompts, a change to how matching
  scores or assigns) need explicit approval from a maintainer in the PR,
  and should start as an issue or discussion. Decisions that shape the
  server are written down in [`docs/adr/`](docs/adr/index.md).
- **Disagreement** is resolved by discussion aiming for consensus; if
  none is reached, the lead maintainer decides and records the rationale.

Every change must pass the full quality gate (100% line+branch coverage,
mypy --strict, ruff, black, CodeQL, the suite conformance test, and the
benchmark still running) before merge - enforced in CI, not by trust. A
change to the matcher reports the growth exponent from
`benches/bench_reconcile.py` before and after, not the milliseconds.

## Releases

Releases follow [`RELEASING.md`](RELEASING.md). reconcile-mcp is
versioned on its own line: versions increment by 0.0.1 and a release is
cut when there is user-visible change to ship. Only maintainers publish
to PyPI; release authority rests with the lead maintainer and is
expanding to a second maintainer as a standing goal.

## Becoming a maintainer

We actively want more maintainers - it is the single biggest thing that
would de-risk the project.

1. Contribute a few reviewed PRs in an area
   ([`ARCHITECTURE.md`](ARCHITECTURE.md) is the map; good first areas:
   the one-to-one matcher's growth on messy data, adapters for further
   suite servers, sandbox scenarios).
2. Help triage issues and review others' PRs.
3. Open an issue (or email the lead maintainer) expressing interest.

A maintainer proposes you; with no objection from existing maintainers
within a week, you are added to `MAINTAINERS.md` for your area.

## Sustainability (bus factor)

reconcile-mcp today has **one** maintainer, which is a real risk for a
tool used in treasury operations. The mitigations in place:

- **The work is legible:** [`ARCHITECTURE.md`](ARCHITECTURE.md) maps the
  codebase, [`RELEASING.md`](RELEASING.md) documents the release process,
  and the tools ship with a runnable example and sandbox scenarios.
- **Quality is enforced by CI,** not by one person's memory.
- **The goal is >= 2 maintainers** with independent release authority.

## Code of conduct & security

Participation is governed by
[`CODE-OF-CONDUCT.md`](CODE-OF-CONDUCT.md). Security issues follow the
private disclosure process in [`SECURITY.md`](SECURITY.md) - please do
not open public issues for vulnerabilities.
