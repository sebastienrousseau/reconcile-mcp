# Copyright (C) 2023-2026 Sebastien Rousseau.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Model Context Protocol (MCP) server for ISO 20022 reconciliation.

This server matches *expected* payments (typically from ``pain.001`` credit
transfers) against *observed* booked entries (typically from a ``camt.053``
statement) and returns an explainable reconciliation report: exact matches,
short/over payments, split settlements (one-to-many), batch credits
(many-to-one) and the residual unmatched items on each side.

Every tool is a thin, typed wrapper over :mod:`reconcile_mcp.engine` (the pure
matching core), :mod:`reconcile_mcp.adapters` (bridges from the rest of the
ISO 20022 suite) and :mod:`reconcile_mcp.sandbox` (deterministic test-mode
fixtures). Tools return JSON-serializable data; on a :class:`ValueError` they
return an ``{"error": ...}`` payload rather than raising.

Launching the server:
    * As a console script::

        reconcile-mcp

    * In an MCP client config (e.g. Claude Desktop)::

        {
          "mcpServers": {
            "reconcile": {
              "command": "reconcile-mcp"
            }
          }
        }

The server communicates over stdio (FastMCP's default transport).
"""

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from reconcile_mcp import __version__, adapters, engine, sandbox

server = FastMCP("reconcile")
# FastMCP does not expose a version kwarg; without this override the MCP SDK's
# own version leaks into serverInfo.version, breaking manifest/runtime
# coherence checks (e.g. Glama scoring).
server._mcp_server.version = __version__

# Every tool here is a pure, side-effect-free reader: it computes solely from
# its arguments (and the bundled sandbox fixtures). Nothing opens a
# caller-supplied path or reaches an external system, so all are marked
# ``readOnlyHint`` + ``idempotentHint``, never ``destructiveHint``, and
# closed-world (``openWorldHint=False``).
_PURE_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

_RECORD_DESC = (
    "List of canonical records. Each is an object with 'id' (string) and "
    "'amount' (number) required, plus optional 'currency' (ISO 4217), 'date' "
    "(ISO-8601), 'counterparty' (name), 'reference' (remittance/end-to-end id)."
)
_OPTIONS_DESC = (
    "Optional tuning object: 'abs_tol'/'rel_tol' (amount tolerance), "
    "'date_window_days', 'high_threshold', 'review_threshold', "
    "'currency_strict', 'enable_one_to_many', 'max_combination'."
)


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Reconcile expected payments against observed bank-statement entries, "
        "returning exact matches, short/over payments, split settlements "
        "(one-to-many), batch credits (many-to-one) and unmatched residuals, "
        "each with an explainable score and reasons."
    ),
)
def reconcile(
    expected: Annotated[list[dict[str, Any]], Field(description=_RECORD_DESC)],
    observed: Annotated[list[dict[str, Any]], Field(description=_RECORD_DESC)],
    options: Annotated[
        dict[str, Any] | None, Field(description=_OPTIONS_DESC)
    ] = None,
) -> dict[str, Any]:
    """Match expected payments to observed entries; return a full report."""
    try:
        return engine.reconcile(expected, observed, options)
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Score a single expected/observed pair and break down every signal "
        "(reference, amount, date, name). A tuning aid -- it explains the "
        "score even for pairs below the review threshold."
    ),
)
def explain_match(
    expected: Annotated[
        dict[str, Any], Field(description="One expected record.")
    ],
    observed: Annotated[
        dict[str, Any], Field(description="One observed record.")
    ],
    options: Annotated[
        dict[str, Any] | None, Field(description=_OPTIONS_DESC)
    ] = None,
) -> dict[str, Any]:
    """Explain the match score between one expected and one observed record."""
    try:
        return engine.explain_pair(expected, observed, options)
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Convert parsed pain.001 payment instructions into canonical expected "
        "records ready to reconcile. Accepts a list of transactions or a dict "
        "wrapping them under 'transactions'/'payments'/'records'."
    ),
)
def normalize_pain001(
    document: Annotated[
        Any, Field(description="Parsed pain.001 document or transaction list.")
    ],
) -> dict[str, Any]:
    """Adapt parsed pain.001 output into expected reconcile records."""
    try:
        return {"expected": adapters.from_pain001(document)}
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Convert parsed camt.053 statement entries into canonical observed "
        "records ready to reconcile. Accepts a list of entries or a dict "
        "wrapping them under 'entries'/'transactions'/'statements'."
    ),
)
def normalize_camt053(
    document: Annotated[
        Any, Field(description="Parsed camt.053 document or entry list.")
    ],
) -> dict[str, Any]:
    """Adapt parsed camt.053 output into observed reconcile records."""
    try:
        return {"observed": adapters.from_camt053(document)}
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    annotations=_PURE_READ,
    description=(
        "List the built-in sandbox scenarios (test-mode fixtures). Each "
        "demonstrates one reconciliation outcome so you can try the flow with "
        "zero real data."
    ),
)
def list_sandbox_scenarios() -> dict[str, Any]:
    """Return the catalogue of deterministic sandbox scenarios."""
    return {
        "scenarios": sandbox.list_scenarios(),
        "magic_references": sandbox.MAGIC_REFERENCES,
    }


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Return the expected/observed inputs for one named sandbox scenario, "
        "so you can inspect or edit the fixture before reconciling."
    ),
)
def load_sandbox_scenario(
    name: Annotated[
        str, Field(description="Scenario name, e.g. 'clean_match'.")
    ],
) -> dict[str, Any]:
    """Return one sandbox scenario's expected and observed record lists."""
    try:
        return sandbox.load_scenario(name)
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    annotations=_PURE_READ,
    description=(
        "Load a named sandbox scenario and immediately reconcile it -- the "
        "one-call way to see a full, explainable result with zero setup. "
        "Great for a first run or a smoke test."
    ),
)
def run_sandbox_scenario(
    name: Annotated[
        str, Field(description="Scenario name, e.g. 'month_end'.")
    ],
    options: Annotated[
        dict[str, Any] | None, Field(description=_OPTIONS_DESC)
    ] = None,
) -> dict[str, Any]:
    """Load a sandbox scenario and return its reconciliation report."""
    try:
        scenario = sandbox.load_scenario(name)
        report = engine.reconcile(
            scenario["expected"], scenario["observed"], options
        )
        report["scenario"] = {
            "name": scenario["name"],
            "demonstrates": scenario["demonstrates"],
            "description": scenario["description"],
        }
        return report
    except ValueError as exc:
        return {"error": str(exc)}


def main() -> None:
    """Run the reconcile MCP server over stdio (the ``reconcile-mcp`` entry)."""
    server.run()


if __name__ == "__main__":
    main()
