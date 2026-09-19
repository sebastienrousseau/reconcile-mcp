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

stdio by default; ``--transport streamable-http`` or ``--transport sse``
listens on ``--host``/``--port`` instead. See :mod:`reconcile_mcp._cli`.
"""

import json
from typing import Annotated, Any

from mcp.types import ToolAnnotations
from pydantic import Field

from reconcile_mcp import __version__, _cli, adapters, engine, sandbox
from reconcile_mcp._mcp_compat import build_server

# The shim picks FastMCP (mcp 1.x) or MCPServer (mcp 2.x) and reports
# the package version in serverInfo either way.
server = build_server("reconcile", __version__)

# Every tool here is a pure, side-effect-free reader: it computes solely from
# its arguments (and the bundled sandbox fixtures). Nothing opens a
# caller-supplied path or reaches an external system, so all are marked
# ``readOnlyHint`` + ``idempotentHint``, never ``destructiveHint``, and
# closed-world (``openWorldHint=False``).
_PURE_READ = ToolAnnotations(  # type: ignore[call-arg]
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


@server.tool(
    title="Match names (probabilistic)",
    annotations=_PURE_READ,
    description=(
        "Score two counterparty names with Jaro-Winkler similarity and report "
        "whether they match at a given threshold. Tolerant of legal-suffix "
        "drift, e.g. 'ACME Corp' vs 'ACME Corporation Inc'."
    ),
)
def match_names_probabilistic(
    name_a: Annotated[str, Field(description="First counterparty name.")],
    name_b: Annotated[str, Field(description="Second counterparty name.")],
    threshold: Annotated[
        float,
        Field(
            description=(
                "Similarity in [0, 1] at or above which the pair is a match."
            )
        ),
    ] = 0.85,
) -> dict[str, Any]:
    """Score two names by Jaro-Winkler similarity and flag a match.

    Args:
        name_a: first counterparty name.
        name_b: second counterparty name.
        threshold: match cutoff in ``[0, 1]``.

    Returns:
        ``{"similarity_score": float, "is_match": bool}``, or ``{"error": ...}``
        if ``threshold`` is out of range.
    """
    try:
        return engine.match_names_probabilistic(name_a, name_b, threshold)
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    title="Match amounts (FX drift)",
    annotations=_PURE_READ,
    description=(
        "Compare two amounts in different currencies, converting one via a "
        "supplied FX rate and matching if the percentage difference is within "
        "tolerance. Uses exact decimal arithmetic."
    ),
)
def match_amounts_with_fx_drift(
    amount_a: Annotated[
        float, Field(description="Amount denominated in currency_a.")
    ],
    currency_a: Annotated[
        str, Field(description="ISO 4217 code of amount_a.")
    ],
    amount_b: Annotated[
        float, Field(description="Amount denominated in currency_b.")
    ],
    currency_b: Annotated[
        str, Field(description="ISO 4217 code of amount_b.")
    ],
    fx_rate: Annotated[
        float,
        Field(
            description=(
                "Units of currency_a per one unit of currency_b (e.g. an "
                "EUR/USD quote of 1.08 is USD per EUR)."
            )
        ),
    ],
    tolerance_pct: Annotated[
        float,
        Field(
            description="Max percentage difference still counted as a match."
        ),
    ] = 1.0,
) -> dict[str, Any]:
    """Compare two cross-currency amounts, tolerating small FX drift.

    Args:
        amount_a: amount in ``currency_a``.
        currency_a: ISO 4217 code of ``amount_a``.
        amount_b: amount in ``currency_b`` to compare against.
        currency_b: ISO 4217 code of ``amount_b``.
        fx_rate: units of ``currency_a`` per one unit of ``currency_b``.
        tolerance_pct: match tolerance as a percentage.

    Returns:
        ``{"converted_amount": str, "difference_pct": float, "is_match":
        bool}``, or ``{"error": ...}`` if ``fx_rate`` is not positive.
    """
    try:
        return engine.match_amounts_with_fx_drift(
            amount_a,
            currency_a,
            amount_b,
            currency_b,
            fx_rate,
            tolerance_pct,
        )
    except ValueError as exc:
        return {"error": str(exc)}


@server.tool(
    title="Reconcile many-to-many",
    annotations=_PURE_READ,
    description=(
        "Match each statement/deposit to a disjoint subset of invoices whose "
        "amounts sum to it (bounded subset-sum solved as an integer program). "
        "Returns matched groups and the unmatched residuals on each side."
    ),
)
def reconcile_many_to_many(
    statements: Annotated[
        list[dict[str, Any]], Field(description=_RECORD_DESC)
    ],
    invoices: Annotated[list[dict[str, Any]], Field(description=_RECORD_DESC)],
) -> dict[str, Any]:
    """Match statement deposits to invoice subsets via subset-sum ILP.

    Args:
        statements: canonical deposit records (each needs ``id`` + ``amount``).
        invoices: canonical invoice records (each needs ``id`` + ``amount``).

    Returns:
        ``{"matches": [...], "unmatched_statements": [...],
        "unmatched_invoices": [...]}``; ``{"error": ...}`` if the optional ILP
        solver is unavailable or a record is malformed.
    """
    try:
        return engine.reconcile_many_to_many(statements, invoices)
    except ValueError as exc:
        return {"error": str(exc)}


@server.prompt(
    title="Reconciliation workflow",
    description=(
        "Step-by-step guidance for driving an end-to-end ISO 20022 "
        "reconciliation with these tools, from raw pain.001/camt.053 through "
        "to an explained match report."
    ),
)
def reconcile_workflow(
    scenario: Annotated[
        str,
        Field(
            description=(
                "Optional sandbox scenario name (e.g. 'clean_match') to walk "
                "through concretely; leave blank for the general workflow."
            )
        ),
    ] = "",
) -> str:
    """Return prose teaching the normalize -> reconcile -> explain workflow."""
    steps = (
        "How to reconcile with this server:\n"
        "1. Normalize your inputs to canonical records. Pass parsed pain.001 "
        "instructions through `normalize_pain001` to get the `expected` list, "
        "and parsed camt.053 entries through `normalize_camt053` to get the "
        "`observed` list. Each canonical record needs an 'id' and 'amount', "
        "plus optional 'currency', 'date', 'counterparty' and 'reference'.\n"
        "2. Reconcile. Call `reconcile` with those `expected` and `observed` "
        "lists (and an optional tuning `options` object) to get exact "
        "matches, short/over payments, split settlements (one-to-many), batch "
        "credits (many-to-one) and the unmatched residuals on each side.\n"
        "3. Explain. For any pair you want to understand or tune, call "
        "`explain_match` on that single expected/observed pair to break down "
        "the reference, amount, date and name signals behind its score."
    )
    if scenario:
        return (
            steps + "\n\nTo see it end-to-end with zero real data, call "
            f"`run_sandbox_scenario` with name={scenario!r}; use "
            "`load_sandbox_scenario` first if you want to inspect or edit its "
            "expected/observed inputs before reconciling."
        )
    return (
        steps + "\n\nTo try the flow with zero real data, browse the built-in "
        "fixtures via `list_sandbox_scenarios`, then `run_sandbox_scenario` "
        "(e.g. name='clean_match') for a full explained result in one call."
    )


@server.resource(
    "reconcile://sandbox-scenarios",
    title="Sandbox scenarios",
    description=(
        "The catalogue of built-in sandbox scenarios and magic references, "
        "as JSON -- the resource form of `list_sandbox_scenarios`."
    ),
    mime_type="application/json",
)
def sandbox_scenarios_resource() -> str:
    """Serialize the sandbox scenario catalogue and magic references."""
    return json.dumps(
        {
            "scenarios": sandbox.list_scenarios(),
            "magic_references": sandbox.MAGIC_REFERENCES,
        }
    )


@server.resource(
    "reconcile://sandbox/{scenario_id}",
    title="Sandbox scenario",
    description=(
        "One named sandbox scenario's expected/observed inputs as JSON -- the "
        "resource form of `load_sandbox_scenario`. Unknown ids return an "
        "'error' payload."
    ),
    mime_type="application/json",
)
def sandbox_scenario_resource(
    scenario_id: Annotated[
        str, Field(description="Scenario name, e.g. 'clean_match'.")
    ],
) -> str:
    """Serialize one sandbox scenario's expected and observed record lists."""
    try:
        return json.dumps(sandbox.load_scenario(scenario_id))
    except ValueError as exc:
        return json.dumps({"error": str(exc)})


def main(argv: list[str] | None = None) -> None:
    """Run the reconcile MCP server (the ``reconcile-mcp`` entry point).

    stdio by default; ``--transport streamable-http`` or ``--transport sse``
    listens on ``--host``/``--port`` instead. See :mod:`reconcile_mcp._cli`.

    Args:
        argv: Command-line arguments; ``None`` reads ``sys.argv[1:]``.
    """
    _cli.serve(server, argv, "reconcile-mcp", __version__)


if __name__ == "__main__":
    main()
