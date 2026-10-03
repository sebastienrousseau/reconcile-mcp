<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Development

Developer entry point for `reconcile-mcp`.

## Setup

```console
git clone https://github.com/sebastienrousseau/reconcile-mcp.git
cd reconcile-mcp
python3 -m venv .venv
source .venv/bin/activate
make dev
```

## Running Verification Gates

```console
make check
```

This runs:
1. `make lint`: `ruff` and `black --check`.
2. `make type-check`: `mypy` strict mode.
3. `make test`: `pytest` with 100% line and branch coverage requirement.
4. `make verify-versions`: proves `pyproject.toml`, `glama.json`, `server.json`, `CITATION.cff`, and `CHANGELOG.md` agree.

## Guidelines

- All commits follow Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.) and signoffs.
- Releases increment strictly by 0.0.1 on `feat/v<next-version>`.
- Dual licensing is maintained under Apache-2.0 OR MIT.
